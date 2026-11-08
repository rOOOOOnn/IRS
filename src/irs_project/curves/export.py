"""Build and export the selected daily curve database."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from irs_project.utils.conventions import (
    business_day_convention_from_name,
    calendar_from_name,
)
from irs_project.utils.dates import from_ql_date, tenor_to_period, to_ql_date

from .bootstrap import build_ois_curve
from .calibration import forward_shape_diagnostics

LOGGER = logging.getLogger(__name__)


def _query_dates(
    valuation_date: pd.Timestamp,
    tenors: list[str],
    config: dict[str, Any],
) -> dict[str, pd.Timestamp]:
    calendar = calendar_from_name(config["curve"]["calendar"])
    convention = business_day_convention_from_name(config["curve"]["business_day_convention"])
    start = to_ql_date(valuation_date)
    return {
        tenor: from_ql_date(calendar.advance(start, tenor_to_period(tenor), convention))
        for tenor in tenors
    }


def build_daily_curve_database(
    market: pd.DataFrame,
    method: str,
    config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    zero_rows: list[dict[str, Any]] = []
    discount_rows: list[dict[str, Any]] = []
    forward_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    tenors = list(config["tenors"])

    for sequence, (_, row) in enumerate(market.iterrows(), start=1):
        valuation_date = pd.Timestamp(row["Date"])
        quotes = {
            tenor: float(row[column])
            for tenor, column in config["tenors"].items()
            if column in row and pd.notna(row[column])
        }
        try:
            curve = build_ois_curve(valuation_date, quotes, method, config)
            dates = _query_dates(valuation_date, tenors, config)
            zero_row: dict[str, Any] = {
                "Date": valuation_date,
                "Interpolation_Method": method,
            }
            discount_row: dict[str, Any] = {
                "Date": valuation_date,
                "Interpolation_Method": method,
            }
            available_dates: dict[str, pd.Timestamp] = {}
            for tenor, maturity in dates.items():
                if maturity <= curve.max_date:
                    zero_row[f"Zero_{tenor}"] = curve.zero_rate(maturity)
                    discount_row[f"DF_{tenor}"] = curve.discount_factor(maturity)
                    available_dates[tenor] = maturity
                else:
                    zero_row[f"Zero_{tenor}"] = np.nan
                    discount_row[f"DF_{tenor}"] = np.nan
            forward_row: dict[str, Any] = {
                "Date": valuation_date,
                "Interpolation_Method": method,
            }
            previous_label = "0"
            previous_date = valuation_date
            for tenor in tenors:
                if tenor in available_dates:
                    forward_row[f"Forward_{previous_label}_{tenor}"] = curve.forward_rate(
                        previous_date, available_dates[tenor]
                    )
                    previous_label = tenor
                    previous_date = available_dates[tenor]
            zero_rows.append(zero_row)
            discount_rows.append(discount_row)
            forward_rows.append(forward_row)
            for calibration in curve.calibration_errors():
                calibration_rows.append({"Date": valuation_date, "Method": method, **calibration})
            diagnostic_rows.append(
                {
                    "Date": valuation_date,
                    "Method": method,
                    "Max_Curve_Date": curve.max_date,
                    **forward_shape_diagnostics(curve),
                }
            )
        except Exception as error:
            failure_rows.append(
                {
                    "Date": valuation_date,
                    "Method": method,
                    "Stage": "DAILY_CURVE",
                    "Failure_Reason": str(error),
                }
            )
        if sequence % 100 == 0 or sequence == len(market):
            LOGGER.info("Daily curve progress: %s/%s", sequence, len(market))

    zero = pd.DataFrame(zero_rows).sort_values("Date").reset_index(drop=True)
    discount = pd.DataFrame(discount_rows).sort_values("Date").reset_index(drop=True)
    forward = pd.DataFrame(forward_rows).sort_values("Date").reset_index(drop=True)
    zero_columns = [column for column in zero if column.startswith("Zero_")]
    changes = zero[["Date", *zero_columns]].copy()
    changes[zero_columns] = changes[zero_columns].diff()
    changes = changes.rename(
        columns={column: column.replace("Zero_", "Delta_Zero_") for column in zero_columns}
    )
    return {
        "zero_curve_panel.csv": zero,
        "discount_factor_panel.csv": discount,
        "forward_rate_panel.csv": forward,
        "zero_rate_changes.csv": changes,
        "curve_calibration.csv": pd.DataFrame(calibration_rows),
        "curve_shape_diagnostics.csv": pd.DataFrame(diagnostic_rows),
        "curve_failures.csv": pd.DataFrame(
            failure_rows,
            columns=["Date", "Method", "Stage", "Failure_Reason"],
        ),
    }


def write_curve_database(outputs: dict[str, pd.DataFrame], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        frame.to_csv(directory / name, index=False, date_format="%Y-%m-%d")
