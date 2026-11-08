"""Load standardized market inputs for curve construction and pricing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .inspect import PROJECT_ROOT


@dataclass(frozen=True)
class MarketDataBundle:
    ois_quotes: pd.DataFrame
    curve_inputs_5y: pd.DataFrame
    sofr_fixings: pd.DataFrame
    sofr_index: pd.DataFrame


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_curve_config(path: Path | None = None) -> dict[str, Any]:
    config = load_yaml(path or PROJECT_ROOT / "config" / "curve.yaml")
    project = load_yaml(PROJECT_ROOT / "config" / "project.yaml")
    config["splits"] = project["splits"]
    return config


def load_contract_config(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or PROJECT_ROOT / "config" / "contract.yaml")


def load_market_data(processed_directory: Path | None = None) -> MarketDataBundle:
    directory = processed_directory or PROJECT_ROOT / "data" / "processed"
    ois_quotes = pd.read_csv(directory / "ois_par_rates_wide.csv", parse_dates=["Date"])
    curve_inputs = pd.read_csv(directory / "ois_curve_inputs_5y.csv", parse_dates=["Date"])
    valid_dates = set(curve_inputs["Date"])
    ois_quotes = ois_quotes.loc[ois_quotes["Date"].isin(valid_dates)].reset_index(drop=True)
    return MarketDataBundle(
        ois_quotes=ois_quotes,
        curve_inputs_5y=curve_inputs,
        sofr_fixings=pd.read_csv(directory / "sofr_fixings.csv", parse_dates=["Date"]),
        sofr_index=pd.read_csv(directory / "sofr_index.csv", parse_dates=["Date"]),
    )


def quotes_for_date(
    ois_quotes: pd.DataFrame,
    valuation_date: pd.Timestamp,
    tenor_mapping: dict[str, str],
) -> dict[str, float]:
    match = ois_quotes.loc[ois_quotes["Date"] == pd.Timestamp(valuation_date)]
    if len(match) != 1:
        raise KeyError(f"Expected one OIS row for {valuation_date.date()}, found {len(match)}")
    row = match.iloc[0]
    return {
        tenor: float(row[column])
        for tenor, column in tenor_mapping.items()
        if column in row.index and pd.notna(row[column])
    }
