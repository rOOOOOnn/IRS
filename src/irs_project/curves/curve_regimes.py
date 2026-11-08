"""Freeze training-sample curve-shape thresholds and classify daily par curves."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RegimeThresholds:
    flat_slope_absolute: float
    curvature_absolute: float


def fit_regime_thresholds(
    training: pd.DataFrame,
    flat_quantile: float,
    curvature_quantile: float,
) -> RegimeThresholds:
    slope = training["OIS_5Y"] - training["OIS_1Y"]
    curvature = 2 * training["OIS_3Y"] - training["OIS_1Y"] - training["OIS_5Y"]
    return RegimeThresholds(
        flat_slope_absolute=float(slope.abs().quantile(flat_quantile)),
        curvature_absolute=float(curvature.abs().quantile(curvature_quantile)),
    )


def classify_curve(row: pd.Series, thresholds: RegimeThresholds) -> str:
    slope = float(row["OIS_5Y"] - row["OIS_1Y"])
    curvature = float(2 * row["OIS_3Y"] - row["OIS_1Y"] - row["OIS_5Y"])
    if curvature > thresholds.curvature_absolute:
        return "HUMPED"
    if curvature < -thresholds.curvature_absolute:
        return "TROUGH"
    if abs(slope) <= thresholds.flat_slope_absolute:
        return "FLAT"
    return "UPWARD" if slope > 0 else "INVERTED"


def add_curve_regimes(
    frame: pd.DataFrame,
    thresholds: RegimeThresholds,
) -> pd.DataFrame:
    result = frame.copy()
    result["Slope_5Y_1Y"] = result["OIS_5Y"] - result["OIS_1Y"]
    result["Curvature_3Y"] = 2 * result["OIS_3Y"] - result["OIS_1Y"] - result["OIS_5Y"]
    result["Curve_Regime"] = result.apply(classify_curve, axis=1, thresholds=thresholds)
    return result
