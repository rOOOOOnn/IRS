"""Leave-one-tenor-out and multi-tenor robustness validation."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import pandas as pd

from irs_project.data.load_market_data import quotes_for_date
from irs_project.data.merge import assign_split

from .bootstrap import build_ois_curve

LOGGER = logging.getLogger(__name__)


def _available_tenors(row: pd.Series, tenor_mapping: dict[str, str]) -> list[str]:
    return [
        tenor
        for tenor, column in tenor_mapping.items()
        if column in row.index and pd.notna(row[column])
    ]


def run_loto_validation(
    market: pd.DataFrame,
    config: dict[str, Any],
    methods: Iterable[str] | None = None,
) -> pd.DataFrame:
    selected_methods = list(methods or config["methods"])
    tenor_mapping = config["tenors"]
    rows: list[dict[str, Any]] = []
    split_labels = assign_split(market["Date"], config["splits"])
    for sequence, ((_, market_row), dataset) in enumerate(
        zip(market.iterrows(), split_labels, strict=True), start=1
    ):
        valuation_date = pd.Timestamp(market_row["Date"])
        available = _available_tenors(market_row, tenor_mapping)
        full_quotes = {tenor: float(market_row[tenor_mapping[tenor]]) for tenor in available}
        for held_tenor in available:
            remaining = {key: value for key, value in full_quotes.items() if key != held_tenor}
            endpoint = held_tenor in {available[0], available[-1]}
            for method in selected_methods:
                record = {
                    "Date": valuation_date,
                    "Dataset": str(dataset),
                    "Method": method,
                    "Held_Out_Tenor": held_tenor,
                    "Evaluation_Type": "ENDPOINT_EXTRAPOLATION" if endpoint else "INTERIOR",
                    "Market_Quote": full_quotes[held_tenor],
                    "Model_Quote": float("nan"),
                    "Error_bps": float("nan"),
                    "Absolute_Error_bps": float("nan"),
                    "Status": "FAILED",
                    "Failure_Reason": "",
                }
                try:
                    curve = build_ois_curve(
                        valuation_date,
                        remaining,
                        method,
                        config,
                        enforce_required_tenors=False,
                        allow_extrapolation=endpoint,
                    )
                    model_quote = curve.par_ois_rate(held_tenor)
                    error_bps = (model_quote - full_quotes[held_tenor]) * 10_000
                    record.update(
                        {
                            "Model_Quote": model_quote,
                            "Error_bps": error_bps,
                            "Absolute_Error_bps": abs(error_bps),
                            "Status": "SUCCESS",
                        }
                    )
                except Exception as error:  # QuantLib raises RuntimeError for failed bootstraps.
                    record["Failure_Reason"] = str(error)
                rows.append(record)
        if sequence % 100 == 0 or sequence == len(market):
            LOGGER.info("LOTO progress: %s/%s dates", sequence, len(market))
    return pd.DataFrame(rows)


def month_end_sample(frame: pd.DataFrame) -> pd.DataFrame:
    sample = frame.copy().sort_values("Date")
    sample["Month"] = sample["Date"].dt.to_period("M")
    return sample.groupby("Month", as_index=False).tail(1).drop(columns="Month")


def run_multi_tenor_holdouts(
    market: pd.DataFrame,
    config: dict[str, Any],
    methods: Iterable[str] | None = None,
) -> pd.DataFrame:
    selected_methods = list(methods or config["methods"])
    sample = month_end_sample(market)
    rows: list[dict[str, Any]] = []
    for _, market_row in sample.iterrows():
        valuation_date = pd.Timestamp(market_row["Date"])
        available = _available_tenors(market_row, config["tenors"])
        full_quotes = quotes_for_date(
            market.loc[market["Date"] == valuation_date],
            valuation_date,
            config["tenors"],
        )
        for holdout in config["validation"]["robustness_holdouts"]:
            if not set(holdout).issubset(available):
                continue
            remaining = {key: value for key, value in full_quotes.items() if key not in holdout}
            for method in selected_methods:
                try:
                    curve = build_ois_curve(
                        valuation_date,
                        remaining,
                        method,
                        config,
                        enforce_required_tenors=False,
                    )
                    for held_tenor in holdout:
                        model_quote = curve.par_ois_rate(held_tenor)
                        error_bps = (model_quote - full_quotes[held_tenor]) * 10_000
                        rows.append(
                            {
                                "Date": valuation_date,
                                "Method": method,
                                "Holdout_Set": "+".join(holdout),
                                "Held_Out_Tenor": held_tenor,
                                "Market_Quote": full_quotes[held_tenor],
                                "Model_Quote": model_quote,
                                "Error_bps": error_bps,
                                "Absolute_Error_bps": abs(error_bps),
                                "Status": "SUCCESS",
                                "Failure_Reason": "",
                            }
                        )
                except Exception as error:
                    rows.append(
                        {
                            "Date": valuation_date,
                            "Method": method,
                            "Holdout_Set": "+".join(holdout),
                            "Held_Out_Tenor": ";".join(holdout),
                            "Status": "FAILED",
                            "Failure_Reason": str(error),
                        }
                    )
    return pd.DataFrame(rows)
