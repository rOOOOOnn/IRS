"""Shape standardized market data and assign chronological research periods."""

from __future__ import annotations

from typing import Any

import pandas as pd


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
