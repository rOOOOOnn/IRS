"""Create traceable standardized files from local Bloomberg Excel exports."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .inspect import (
    PROJECT_ROOT,
    configured_path,
    discover_workbooks,
    inspect_directory,
    load_config,
    read_workbook,
)
from .merge import assign_split, ois_long_to_wide


def infer_rate_decimal(values: pd.Series) -> tuple[pd.Series, str]:
    valid = values.dropna().abs()
    if not valid.empty and valid.quantile(0.99) <= 100 and valid.median() > 0.1:
        return values / 100.0, "UNIT_INFERRED_PERCENT"
    return pd.Series(np.nan, index=values.index, dtype=float), "UNIT_UNVERIFIED"


def robust_jump_mask(values: pd.Series) -> pd.Series:
    differences = values.diff().abs()
    valid_differences = differences.dropna()
    if valid_differences.empty:
        return pd.Series(False, index=values.index)
    median = valid_differences.median()
    mad = (valid_differences - median).abs().median()
    robust_limit = median + 10 * 1.4826 * mad
    threshold = max(0.25, float(robust_limit))
    return differences > threshold


def _combine_flags(flag_sets: list[set[str]]) -> list[str]:
    return [";".join(sorted(flags)) if flags else "OK" for flags in flag_sets]


def standardize_series(series: Any, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = series.observations[["Date", "Value"]].copy().sort_values("Date")
    frame["Ticker"] = series.canonical_ticker
    frame["Tenor"] = series.series_config["tenor"]
    frame["Kind"] = series.series_config["kind"]
    frame["Source"] = f"Bloomberg:{series.path.relative_to(PROJECT_ROOT).as_posix()}"
    frame["Field"] = series.field
    frame["Security_Description"] = (
        series.metadata.get("Security Description") or series.metadata.get("Security") or ""
    )

    flag_sets = [set() for _ in range(len(frame))]
    duplicate_mask = frame["Date"].duplicated(keep=False)
    missing_mask = frame["Value"].isna()
    weekend_mask = frame["Date"].dt.dayofweek >= 5
    for position in np.flatnonzero(duplicate_mask.to_numpy()):
        flag_sets[position].add("DUPLICATE_DATE")
    for position in np.flatnonzero(missing_mask.to_numpy()):
        flag_sets[position].add("MISSING_VALUE")
    for position in np.flatnonzero(weekend_mask.to_numpy()):
        flag_sets[position].add("WEEKEND_OBSERVATION")

    if series.series_config["kind"] == "OIS_PAR_RATE":
        pre_sofr_mask = frame["Date"] < pd.Timestamp(config["data"]["main_sample_start"])
        for position in np.flatnonzero(pre_sofr_mask.to_numpy()):
            flag_sets[position].add("PRE_SOFR_UNVERIFIED")

    if series.series_config["kind"] == "SOFR_INDEX":
        frame["Rate_Decimal"] = np.nan
        unit_flag = None
    else:
        frame["Rate_Decimal"], unit_flag = infer_rate_decimal(frame["Value"])
        if unit_flag:
            for flags in flag_sets:
                flags.add(unit_flag)

    jump_mask = robust_jump_mask(frame["Value"])
    for position in np.flatnonzero(jump_mask.to_numpy()):
        flag_sets[position].add("OUTLIER_JUMP_REVIEW")

    frame["Quality_Flag"] = _combine_flags(flag_sets)
    review_mask = frame["Quality_Flag"].map(
        lambda value: any(
            flag not in {"OK", "UNIT_INFERRED_PERCENT"} for flag in value.split(";")
        )
    )
    anomalies = frame.loc[review_mask, ["Date", "Ticker", "Value", "Quality_Flag", "Source"]].copy()
    anomalies = anomalies.rename(columns={"Value": "Value_Raw", "Quality_Flag": "Issue"})

    # Standardized interfaces require one date per series. Keep the first source row and
    # retain every duplicate in anomaly_records.csv and the immutable raw workbook.
    frame = frame.drop_duplicates(["Date", "Ticker"], keep="first")
    return frame, anomalies


def missingness_report(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid_dates_by_ticker = {
        frame["Ticker"].iloc[0]: set(frame.loc[frame["Value"].notna(), "Date"])
        for frame in frames
        if not frame.empty
    }
    union_dates = set().union(*valid_dates_by_ticker.values()) if valid_dates_by_ticker else set()
    rows = []
    for frame in frames:
        if frame.empty:
            continue
        ticker = frame["Ticker"].iloc[0]
        source_dates = set(frame["Date"])
        rows.append(
            {
                "Ticker": ticker,
                "Rows_With_Date": len(frame),
                "Source_Missing_Values": int(frame["Value"].isna().sum()),
                "Missing_On_Another_Series_Observed_Date": len(union_dates - source_dates),
                "Weekend_Observations": int((frame["Date"].dt.dayofweek >= 5).sum()),
                "Gap_Interpretation": "UNRESOLVED_NONTRADING_OR_SOURCE_GAP",
            }
        )
    return pd.DataFrame(rows)


def split_summary(frames: list[pd.DataFrame], config: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for frame in frames:
        valid = frame.loc[frame["Value"].notna()].copy()
        valid["Split"] = assign_split(valid["Date"], config["splits"])
        for split_name, group in valid.groupby("Split", dropna=False):
            rows.append(
                {
                    "Ticker": frame["Ticker"].iloc[0],
                    "Split": split_name,
                    "First_Observation": group["Date"].min(),
                    "Last_Observation": group["Date"].max(),
                    "Valid_Observations": len(group),
                }
            )
    return pd.DataFrame(rows)


def wide_split_summary(wide: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    dated = wide.copy()
    dated["Split"] = assign_split(dated["Date"], config["splits"])
    value_columns = [column for column in dated.columns if column.startswith("OIS_")]
    rows = []
    for split_name, group in dated.groupby("Split", dropna=False):
        if split_name == "OUTSIDE_PRESET_SPLITS":
            continue
        for label, mask in (
            ("ALL_OIS_DATES", group[value_columns].notna().any(axis=1)),
            ("COMPLETE_10_TENOR_CURVE", group[value_columns].notna().all(axis=1)),
        ):
            selected = group.loc[mask]
            rows.append(
                {
                    "Ticker": label,
                    "Split": split_name,
                    "First_Observation": selected["Date"].min() if not selected.empty else pd.NaT,
                    "Last_Observation": selected["Date"].max() if not selected.empty else pd.NaT,
                    "Valid_Observations": len(selected),
                }
            )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No records."
    display = frame.copy()
    display = display.fillna("")
    headers = [str(column) for column in display.columns]
    rows = [headers, ["---"] * len(headers)]
    for values in display.astype(str).itertuples(index=False, name=None):
        rows.append([value.replace("|", "\\|").replace("\n", " ") for value in values])
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def build_quality_report(
    coverage: pd.DataFrame,
    missingness: pd.DataFrame,
    anomalies: pd.DataFrame,
    split_counts: pd.DataFrame,
) -> str:
    lines = [
        "# Bloomberg Raw Data Quality Report",
        "",
        "## Scope",
        "",
        f"Inspected {len(coverage)} canonical series. Raw workbooks remain unchanged and local.",
        "",
        "## Key Findings",
        "",
        (
            "- Bloomberg exports provide Security, date range, frequency, and "
            "PX_LAST/PX_BID fields, but no explicit unit field or Security Description."
        ),
        (
            "- Rate units are inferred as percentage points from ticker meaning and "
            "observed magnitude; every converted rate retains `UNIT_INFERRED_PERCENT`."
        ),
        "- SOFR Index is preserved as an index and is never converted to a rate.",
        (
            "- USOSFR observations before 2018-04-02 are retained and flagged "
            "`PRE_SOFR_UNVERIFIED`; they are excluded from the main wide OIS sample."
        ),
        (
            "- Missing values and robust jump candidates are reported, not filled, "
            "deleted, interpolated, or winsorized."
        ),
        (
            "- Calendar gaps cannot be classified as holidays versus source failures "
            "without an approved market calendar; they remain unresolved."
        ),
        "",
        "## Coverage",
        "",
        markdown_table(coverage),
        "",
        "## Missingness",
        "",
        markdown_table(missingness),
        "",
        "## Quality Flags",
        "",
        markdown_table(
            anomalies["Issue"].value_counts().rename_axis("Issue").reset_index(name="Rows")
        )
        if not anomalies.empty
        else "No flagged rows.",
        "",
        "## Chronological Split Counts",
        "",
        markdown_table(split_counts),
        "",
        "## Manual Confirmation Required",
        "",
        (
            "1. Confirm Bloomberg security descriptions and units from an authoritative "
            "Bloomberg screen or field-definition export."
        ),
        (
            "2. Determine what the pre-2018 USOSFR history represents before any use "
            "in the SOFR OIS sample."
        ),
        (
            "3. Confirm the appropriate USD OIS business calendar before classifying "
            "absent weekdays as true missing observations."
        ),
        (
            "4. Review every `OUTLIER_JUMP_REVIEW` record against the original source "
            "and market events."
        ),
    ]
    return "\n".join(lines) + "\n"


def run_pipeline(config: dict[str, Any]) -> None:
    output_directory = configured_path(config, "processed_directory")
    report_directory = configured_path(config, "report_directory")
    output_directory.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)

    manifest, coverage = inspect_directory(config)
    standardized_frames: list[pd.DataFrame] = []
    anomaly_frames: list[pd.DataFrame] = []

    for path in discover_workbooks(configured_path(config, "raw_directory")):
        if path.name.lower().startswith("grid_"):
            continue
        series = read_workbook(path, config)
        if not series.canonical_ticker:
            continue
        standardized, anomalies = standardize_series(series, config)
        standardized_frames.append(standardized)
        anomaly_frames.append(anomalies)

    if not standardized_frames:
        raise RuntimeError("No canonical Bloomberg workbooks were found")

    combined = pd.concat(standardized_frames, ignore_index=True)
    anomalies = pd.concat(anomaly_frames, ignore_index=True)
    ois = combined.loc[combined["Kind"] == "OIS_PAR_RATE"].copy()
    fixing = combined.loc[combined["Kind"] == "SOFR_FIXING"].copy()
    index = combined.loc[combined["Kind"] == "SOFR_INDEX"].copy()

    ois_long = ois.rename(columns={"Value": "Rate_Raw"})[
        [
            "Date",
            "Ticker",
            "Tenor",
            "Rate_Raw",
            "Rate_Decimal",
            "Source",
            "Field",
            "Security_Description",
            "Quality_Flag",
        ]
    ]
    ois_wide = ois_long_to_wide(ois_long, pd.Timestamp(config["data"]["main_sample_start"]))
    sofr_fixings = fixing.rename(columns={"Value": "SOFR_Raw", "Rate_Decimal": "SOFR_Decimal"})[
        ["Date", "SOFR_Raw", "SOFR_Decimal", "Quality_Flag"]
    ]
    sofr_index = index.rename(columns={"Value": "SOFR_Index"})[
        ["Date", "SOFR_Index", "Quality_Flag"]
    ]
    missingness = missingness_report(standardized_frames)
    split_counts = pd.concat(
        [split_summary(standardized_frames, config), wide_split_summary(ois_wide, config)],
        ignore_index=True,
    )

    outputs = {
        "ois_quotes_long.csv": ois_long,
        "ois_par_rates_wide.csv": ois_wide,
        "sofr_fixings.csv": sofr_fixings,
        "sofr_index.csv": sofr_index,
        "data_coverage.csv": coverage,
        "data_manifest.csv": manifest,
        "missingness_report.csv": missingness,
        "anomaly_records.csv": anomalies,
        "dataset_split_summary.csv": split_counts,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_directory / name, index=False, date_format="%Y-%m-%d")

    report = build_quality_report(coverage, missingness, anomalies, split_counts)
    (report_directory / "data_quality_report.md").write_text(report, encoding="utf-8")
    print(f"Processed {len(standardized_frames)} series into {output_directory}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    arguments = parser.parse_args()
    run_pipeline(load_config(arguments.config))


if __name__ == "__main__":
    main()
