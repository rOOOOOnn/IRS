"""Validate market inputs required by the curve and pricing engines."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def validate_curve_inputs(
    frame: pd.DataFrame,
    curve_config: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    required_tenors = curve_config["required_pricing_tenors"]
    mapping = curve_config["tenors"]
    required_columns = [mapping[tenor] for tenor in required_tenors]
    missing_columns = [column for column in ["Date", *required_columns] if column not in frame]
    if missing_columns:
        return [f"Missing curve-input columns: {missing_columns}"]
    if frame["Date"].duplicated().any():
        errors.append("Curve inputs contain duplicate dates")
    if not frame["Date"].is_monotonic_increasing:
        errors.append("Curve input dates are not sorted ascending")
    if frame[required_columns].isna().any().any():
        errors.append("Required 1M-5Y curve inputs contain missing values")
    numeric = frame[required_columns].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        errors.append("Curve inputs contain non-finite values")
    if (numeric < -0.10).any() or (numeric > 0.30).any():
        errors.append("Curve inputs contain rates outside the broad -10% to 30% validity range")
    return errors


def validate_fixings(fixings: pd.DataFrame, index: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    for label, frame, value_column in (
        ("SOFR fixings", fixings, "SOFR_Decimal"),
        ("SOFR index", index, "SOFR_Index"),
    ):
        if frame["Date"].duplicated().any():
            errors.append(f"{label} contain duplicate dates")
        if frame[value_column].isna().any():
            errors.append(f"{label} contain missing values")
        if not frame["Date"].is_monotonic_increasing:
            errors.append(f"{label} dates are not sorted ascending")
    if (index["SOFR_Index"] <= 0).any():
        errors.append("SOFR index must be positive")
    return errors
