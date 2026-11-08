"""Aggregate validation errors and select a defensible global method."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd


def error_metrics(group: pd.DataFrame) -> pd.Series:
    errors = pd.to_numeric(group["Error_bps"], errors="coerce").dropna()
    absolute = errors.abs()
    if errors.empty:
        return pd.Series(
            {
                "MAE_bps": np.nan,
                "RMSE_bps": np.nan,
                "Median_AE_bps": np.nan,
                "P95_AE_bps": np.nan,
                "Max_AE_bps": np.nan,
                "Sample_Count": 0,
            }
        )
    return pd.Series(
        {
            "MAE_bps": float(absolute.mean()),
            "RMSE_bps": float(np.sqrt(np.mean(np.square(errors)))),
            "Median_AE_bps": float(absolute.median()),
            "P95_AE_bps": float(absolute.quantile(0.95)),
            "Max_AE_bps": float(absolute.max()),
            "Sample_Count": len(errors),
        }
    )


def summarize_errors(frame: pd.DataFrame, groups: Iterable[str]) -> pd.DataFrame:
    successful = frame.loc[frame["Status"] == "SUCCESS"].copy()
    return (
        successful.groupby(list(groups), dropna=False)
        .apply(error_metrics, include_groups=False)
        .reset_index()
    )


def select_global_method(
    comparison: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[str, pd.DataFrame]:
    dataset = config["validation"]["method_selection_dataset"]
    metric = config["validation"]["method_selection_metric"]
    eligible = comparison.loc[comparison["Dataset"] == dataset].copy()
    if eligible.empty:
        raise ValueError(f"No {dataset} comparison rows are available for method selection")
    eligible = eligible.sort_values([metric, "Method"]).reset_index(drop=True)
    return str(eligible.loc[0, "Method"]), eligible


def attach_regime(loto: pd.DataFrame, regime_frame: pd.DataFrame) -> pd.DataFrame:
    lookup = regime_frame[["Date", "Curve_Regime"]].drop_duplicates("Date")
    return loto.merge(lookup, on="Date", how="left", validate="many_to_one")
