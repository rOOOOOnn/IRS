from __future__ import annotations

from math import isfinite

import pandas as pd
import pytest

from irs_project.curves.bootstrap import build_ois_curve
from irs_project.curves.calibration import forward_shape_diagnostics
from irs_project.curves.comparison import error_metrics
from irs_project.curves.export import build_daily_curve_database
from irs_project.data.load_market_data import load_curve_config, load_market_data

VALUATION_DATE = pd.Timestamp("2023-05-01")
QUOTES = {
    "1M": 0.050473,
    "3M": 0.0511225,
    "6M": 0.05121,
    "1Y": 0.0488865,
    "2Y": 0.041453,
    "3Y": 0.0375465,
    "4Y": 0.0355395,
    "5Y": 0.034445,
    "7Y": 0.0334525,
    "10Y": 0.0331125,
}


@pytest.mark.parametrize(
    "method",
    [
        "linear_zero",
        "log_linear_discount",
        "natural_cubic_zero",
        "monotone_convex_forward",
    ],
)
def test_each_curve_calibrates_and_queries(method: str) -> None:
    config = load_curve_config()
    curve = build_ois_curve(VALUATION_DATE, QUOTES, method, config)
    errors = curve.calibration_errors()
    assert max(abs(row["Error_bps"]) for row in errors) < 1e-4
    maturity = pd.Timestamp("2025-05-01")
    assert curve.discount_factor(maturity) > 0
    assert isfinite(curve.zero_rate(maturity))
    assert isfinite(curve.forward_rate(pd.Timestamp("2024-05-01"), maturity))


def test_negative_rates_are_supported() -> None:
    config = load_curve_config()
    quotes = {tenor: -0.001 + index * 0.00005 for index, tenor in enumerate(QUOTES)}
    curve = build_ois_curve(VALUATION_DATE, quotes, "log_linear_discount", config)
    assert curve.discount_factor(pd.Timestamp("2024-05-01")) > 1.0


def test_loto_curve_does_not_use_hidden_quote() -> None:
    config = load_curve_config()
    remaining = {tenor: quote for tenor, quote in QUOTES.items() if tenor != "3Y"}
    curve = build_ois_curve(
        VALUATION_DATE,
        remaining,
        "linear_zero",
        config,
        enforce_required_tenors=False,
    )
    assert "3Y" not in curve.instruments.tenors
    assert isfinite(curve.par_ois_rate("3Y"))


def test_forward_shape_diagnostic_is_finite() -> None:
    config = load_curve_config()
    curve = build_ois_curve(VALUATION_DATE, QUOTES, "log_linear_discount", config)
    diagnostic = forward_shape_diagnostics(curve)
    assert diagnostic["Sample_Count"] > 0
    assert isfinite(diagnostic["Forward_Min"])
    assert isfinite(diagnostic["Forward_Max"])


def test_error_metrics_are_correct() -> None:
    frame = pd.DataFrame({"Error_bps": [-1.0, 1.0, 2.0]})
    metrics = error_metrics(frame)
    assert metrics["MAE_bps"] == pytest.approx(4 / 3)
    assert metrics["RMSE_bps"] == pytest.approx((6 / 3) ** 0.5)
    assert metrics["Sample_Count"] == 3


def test_empty_daily_curve_failure_output_keeps_schema() -> None:
    config = load_curve_config()
    market = load_market_data().ois_quotes.head(1)
    outputs = build_daily_curve_database(market, "monotone_convex_forward", config)
    failures = outputs["curve_failures.csv"]
    assert list(failures.columns) == ["Date", "Method", "Stage", "Failure_Reason"]
    assert failures.empty
