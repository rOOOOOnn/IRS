"""Inspect Bloomberg-style Excel exports without changing source files."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class WorkbookSeries:
    path: Path
    metadata: dict[str, Any]
    header_row: int
    field: str
    canonical_ticker: str | None
    series_config: dict[str, Any] | None
    observations: pd.DataFrame


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or PROJECT_ROOT / "config" / "project.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def configured_path(config: dict[str, Any], key: str) -> Path:
    return PROJECT_ROOT / config["data"][key]


def discover_workbooks(raw_directory: Path) -> list[Path]:
    return sorted(path for path in raw_directory.rglob("*.xlsx") if not path.name.startswith("~$"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_token(value: Any) -> str:
    return "".join(character for character in str(value).upper() if character.isalnum())


def resolve_series(
    path: Path, metadata: dict[str, Any], config: dict[str, Any]
) -> tuple[str | None, dict[str, Any] | None]:
    filename_token = _normalise_token(path.stem)
    security_root = str(metadata.get("Security", "")).strip().split()[0]
    security_token = _normalise_token(security_root)
    for ticker, series_config in config["series"].items():
        aliases = {_normalise_token(alias) for alias in series_config.get("aliases", [])}
        aliases.add(_normalise_token(ticker))
        if filename_token in aliases or security_token in aliases:
            return ticker, series_config
    return None, None


def _find_header_row(frame: pd.DataFrame) -> int:
    for index, value in frame.iloc[:, 0].items():
        if str(value).strip().lower() == "date":
            return int(index)
    raise ValueError("No row beginning with 'Date' was found")


def read_workbook(path: Path, config: dict[str, Any]) -> WorkbookSeries:
    frame = pd.read_excel(path, sheet_name=0, header=None, dtype=object, engine="openpyxl")
    header_row = _find_header_row(frame)
    metadata: dict[str, Any] = {}
    for _, row in frame.iloc[:header_row, :2].iterrows():
        key = row.iloc[0]
        if pd.notna(key):
            metadata[str(key).strip()] = row.iloc[1] if len(row) > 1 else None

    headers = [str(value).strip() if pd.notna(value) else "" for value in frame.iloc[header_row]]
    field = (
        "PX_LAST"
        if "PX_LAST" in headers
        else next((header for header in headers[1:] if header), "")
    )
    if not field:
        raise ValueError("No market-data field was found after the Date column")

    date_index = headers.index("Date")
    field_index = headers.index(field)
    observations = pd.DataFrame(
        {
            "Date": pd.to_datetime(frame.iloc[header_row + 1 :, date_index], errors="coerce"),
            "Value_Raw_Cell": frame.iloc[header_row + 1 :, field_index],
        }
    )
    observations = observations.loc[observations["Date"].notna()].copy()
    observations["Value"] = pd.to_numeric(observations["Value_Raw_Cell"], errors="coerce")
    observations["Date"] = observations["Date"].dt.normalize()

    ticker, series_config = resolve_series(path, metadata, config)
    return WorkbookSeries(
        path=path,
        metadata=metadata,
        header_row=header_row,
        field=field,
        canonical_ticker=ticker,
        series_config=series_config,
        observations=observations,
    )


def coverage_record(series: WorkbookSeries, main_sample_start: pd.Timestamp) -> dict[str, Any]:
    observations = series.observations
    valid = observations.loc[observations["Value"].notna()]
    duplicate_dates = int(observations["Date"].duplicated(keep=False).sum())
    pre_sofr = 0
    if series.series_config and series.series_config["kind"] == "OIS_PAR_RATE":
        pre_sofr = int((valid["Date"] < main_sample_start).sum())

    sorted_dates = valid["Date"].drop_duplicates().sort_values()
    median_gap = sorted_dates.diff().dt.days.median() if len(sorted_dates) > 1 else None
    metadata_end = pd.to_datetime(series.metadata.get("End Date"), errors="coerce")
    last_valid = valid["Date"].max() if not valid.empty else pd.NaT

    return {
        "File_Name": series.path.name,
        "Ticker": series.canonical_ticker,
        "Security": series.metadata.get("Security"),
        "Security_Description": series.metadata.get("Security Description"),
        "Field": series.field,
        "Pricing_Source": series.metadata.get("Pricing Source"),
        "Period_Metadata": series.metadata.get("Period"),
        "Metadata_Start_Date": series.metadata.get("Start Date"),
        "Metadata_End_Date": series.metadata.get("End Date"),
        "First_Valid_Observation": valid["Date"].min() if not valid.empty else pd.NaT,
        "Last_Valid_Observation": last_valid,
        "Rows_With_Date": len(observations),
        "Valid_Observations": len(valid),
        "Missing_Values": int(observations["Value"].isna().sum()),
        "Duplicate_Date_Rows": duplicate_dates,
        "Pre_SOFR_Valid_Observations": pre_sofr,
        "Median_Calendar_Gap_Days": median_gap,
        "Frequency_Inference": "BUSINESS_DAILY" if median_gap in {1, 3} else "IRREGULAR_DAILY",
        "Unit_Status": _unit_status(series),
        "Metadata_End_After_Last_Valid": bool(
            pd.notna(metadata_end)
            and pd.notna(last_valid)
            and metadata_end.normalize() > last_valid
        ),
    }


def _unit_status(series: WorkbookSeries) -> str:
    if not series.series_config:
        return "UNMAPPED"
    if series.series_config["kind"] == "SOFR_INDEX":
        return "INDEX_NOT_RATE"
    valid = series.observations["Value"].dropna().abs()
    if not valid.empty and valid.quantile(0.99) <= 100 and valid.median() > 0.1:
        return "PERCENT_INFERRED_FROM_TICKER_AND_MAGNITUDE"
    return "UNIT_UNVERIFIED"


def inspect_directory(config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_directory = configured_path(config, "raw_directory")
    main_sample_start = pd.Timestamp(config["data"]["main_sample_start"])
    manifest_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    for path in discover_workbooks(raw_directory):
        try:
            series = read_workbook(path, config)
            archive_file = path.name.lower().startswith("grid_")
            status = "ARCHIVE_NOT_PROCESSED" if archive_file else "READY"
            if series.canonical_ticker is None:
                status = "UNMAPPED_NOT_PROCESSED"
            manifest_rows.append(
                {
                    "File_Name": path.name,
                    "Relative_Path": path.relative_to(PROJECT_ROOT).as_posix(),
                    "SHA256": file_sha256(path),
                    "Ticker": series.canonical_ticker,
                    "Security": series.metadata.get("Security"),
                    "Field": series.field,
                    "Processing_Status": status,
                }
            )
            if not archive_file and series.canonical_ticker:
                coverage_rows.append(coverage_record(series, main_sample_start))
        except Exception as error:  # retain a manifest record for unreadable source files
            manifest_rows.append(
                {
                    "File_Name": path.name,
                    "Relative_Path": path.relative_to(PROJECT_ROOT).as_posix(),
                    "SHA256": file_sha256(path),
                    "Ticker": None,
                    "Security": None,
                    "Field": None,
                    "Processing_Status": f"ERROR: {error}",
                }
            )

    return pd.DataFrame(manifest_rows), pd.DataFrame(coverage_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    arguments = parser.parse_args()
    config = load_config(arguments.config)
    output_directory = configured_path(config, "processed_directory")
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest, coverage = inspect_directory(config)
    manifest.to_csv(output_directory / "data_manifest.csv", index=False, date_format="%Y-%m-%d")
    coverage.to_csv(output_directory / "data_coverage.csv", index=False, date_format="%Y-%m-%d")
    print(f"Inspected {len(manifest)} workbooks; {len(coverage)} canonical series are ready.")


if __name__ == "__main__":
    main()
