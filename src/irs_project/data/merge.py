"""Shape standardized market data and assign chronological research periods."""

from __future__ import annotations

from typing import Any

import pandas as pd

ALL_TENOR_COLUMNS = [
    "OIS_1M",
    "OIS_3M",
    "OIS_6M",
    "OIS_1Y",
    "OIS_2Y",
    "OIS_3Y",
    "OIS_4Y",
    "OIS_5Y",
    "OIS_7Y",
    "OIS_10Y",
]
REQUIRED_5Y_CURVE_COLUMNS = ALL_TENOR_COLUMNS[:8]
OPTIONAL_LONG_END_COLUMNS = ALL_TENOR_COLUMNS[8:]


def assign_split(dates: pd.Series, split_config: dict[str, Any]) -> pd.Series:
    result = pd.Series("OUTSIDE_PRESET_SPLITS", index=dates.index, dtype="string")
    normalized = pd.to_datetime(dates, errors="coerce")
    for name, bounds in split_config.items():
        start = pd.Timestamp(bounds["start"])
        end = pd.Timestamp(bounds["end"]) if bounds.get("end") else pd.Timestamp.max.normalize()
        result.loc[normalized.between(start, end, inclusive="both")] = name.upper()
    return result


def ois_long_to_wide(ois_long: pd.DataFrame, main_sample_start: pd.Timestamp) -> pd.DataFrame:
    sample = ois_long.loc[ois_long["Date"] >= main_sample_start].copy()
    sample = sample.drop_duplicates(["Date", "Ticker"], keep="first")
    wide = sample.pivot(index="Date", columns="Tenor", values="Rate_Decimal")
    tenor_order = ["1M", "3M", "6M", "1Y", "2Y", "3Y", "4Y", "5Y", "7Y", "10Y"]
    wide = wide.reindex(columns=tenor_order).rename(columns=lambda tenor: f"OIS_{tenor}")
    return wide.sort_index().reset_index()


def apply_five_year_curve_policy(
    wide: pd.DataFrame, split_config: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Require observed 1M-5Y nodes while treating 7Y and 10Y as optional."""
    missing = wide[ALL_TENOR_COLUMNS].isna()
    required_missing = missing[REQUIRED_5Y_CURVE_COLUMNS]
    incomplete_mask = required_missing.any(axis=1)

    incomplete = wide.loc[incomplete_mask, ["Date"]].copy()
    incomplete["Missing_Required_Tenor_Count"] = (
        required_missing.loc[incomplete_mask].sum(axis=1).astype(int)
    )
    incomplete["Missing_Required_Tenors"] = required_missing.loc[incomplete_mask].apply(
        lambda row: ";".join(
            column.removeprefix("OIS_") for column in REQUIRED_5Y_CURVE_COLUMNS if row[column]
        ),
        axis=1,
    )
    incomplete["Split"] = assign_split(incomplete["Date"], split_config)
    incomplete["Treatment"] = "DROPPED_FROM_COMPLETE_CURVE_PANEL"

    total_dates = len(wide)
    by_tenor = pd.DataFrame(
        {
            "Tenor": [column.removeprefix("OIS_") for column in ALL_TENOR_COLUMNS],
            "Total_Dates": total_dates,
            "Missing_Dates": [int(missing[column].sum()) for column in ALL_TENOR_COLUMNS],
            "Required_For_5Y_Curve": [
                column in REQUIRED_5Y_CURVE_COLUMNS for column in ALL_TENOR_COLUMNS
            ],
        }
    )
    denominator = total_dates if total_dates else 1
    by_tenor["Missing_Rate"] = by_tenor["Missing_Dates"] / denominator
    by_tenor["Treatment"] = by_tenor["Required_For_5Y_Curve"].map(
        {True: "DROP_DATE_IF_MISSING", False: "OPTIONAL_RETAIN_DATE"}
    )

    curve_inputs = (
        wide.loc[~incomplete_mask, ["Date", *REQUIRED_5Y_CURVE_COLUMNS]]
        .copy()
        .reset_index(drop=True)
    )
    return curve_inputs, incomplete.reset_index(drop=True), by_tenor
