from __future__ import annotations

from dataclasses import replace
from math import exp, log

import pandas as pd
import pytest

from irs_project.curves.export import tenor_dates
from irs_project.data.load_market_data import load_contract_config, load_curve_config
from irs_project.pricing.contract import IRSContract
from irs_project.pricing.floating_leg import SofrHistory
from irs_project.pricing.scenario_repricing import build_scenario_curve
from irs_project.pricing.schedule import build_payment_schedules
from irs_project.pricing.valuation import price_irs
from irs_project.utils.dates import to_ql_date


class FlatCurve:
    def __init__(self, valuation_date: str, rate: float) -> None:
        self.valuation_date = pd.Timestamp(valuation_date)
        self.rate = rate

    def _time(self, value: object) -> float:
        return (pd.Timestamp(value) - self.valuation_date).days / 365.0

    def discount_factor(self, value: object) -> float:
        return exp(-self.rate * self._time(value))

    def zero_rate(self, value: object) -> float:
        return self.rate

    def forward_rate(self, start: object, end: object) -> float:
        return -log(self.discount_factor(end) / self.discount_factor(start)) / (
            self._time(end) - self._time(start)
        )


def _contract() -> IRSContract:
    return IRSContract.from_config(load_contract_config())


def _history() -> SofrHistory:
    dates = pd.to_datetime(["2023-05-01", "2024-05-01", "2025-05-01", "2026-05-01", "2027-05-03"])
    index = pd.Series([1.0, 1.05, 1.10, 1.15, 1.20], index=dates)
    return SofrHistory(fixings=pd.Series(dtype=float), index=index)


def test_contract_uses_disclosed_payment_frequencies() -> None:
    schedules = build_payment_schedules(_contract())
    assert len(schedules.fixed) == 10
    assert len(schedules.floating) == 20
    assert schedules.floating[0].payment_date < schedules.fixed[0].payment_date


def test_pay_fixed_receive_floating_sign() -> None:
    contract = _contract()
    curve = FlatCurve("2023-05-01", 0.05)
    valuation = price_irs(pd.Timestamp("2023-05-01"), curve, contract, _history())
    assert valuation.market_value == pytest.approx(valuation.pv_floating - valuation.pv_fixed)
    assert valuation.status == "SUCCESS"


def test_realized_factor_rejects_future_information() -> None:
    with pytest.raises(ValueError, match="after the valuation date"):
        _history().realized_factor(
            pd.Timestamp("2023-05-01"),
            pd.Timestamp("2024-05-01"),
            pd.Timestamp("2023-12-31"),
        )


def test_positive_parallel_scenario_shock_changes_value() -> None:
    contract = _contract()
    curve = FlatCurve("2023-05-01", 0.04)
    config = load_curve_config()
    shocks = {tenor: 0.001 for tenor in config["required_pricing_tenors"]}
    scenario = build_scenario_curve(pd.Timestamp("2023-05-01"), curve, shocks, config)
    assert scenario.zero_rate(pd.Timestamp("2025-05-01")) == pytest.approx(0.041)
    base = price_irs(pd.Timestamp("2023-05-01"), curve, contract, _history())
    shocked = price_irs(pd.Timestamp("2023-05-01"), scenario, contract, _history())
    assert shocked.market_value != pytest.approx(base.market_value)



@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observation_lookback_days", 1),
        ("observation_lookback_days", 0.5),
        ("observation_shift", True),
        ("lockout_days", 1),
    ],
)
def test_unsupported_sofr_conventions_are_rejected(field, value):
    contract = _contract()
    contract.validate()
    with pytest.raises(ValueError, match=field):
        replace(contract, **{field: value}).validate()
    config = load_contract_config()
    config["contract"][field]["value"] = value
    with pytest.raises(ValueError, match=field):
        IRSContract.from_config(config).validate()


def test_elapsed_carry_uses_prior_curve_and_keeps_published_index_intact():
    anchor = pd.Timestamp("2023-05-01")
    holiday = pd.Timestamp("2023-05-02")
    future = pd.Timestamp("2024-05-01")
    source = _history()
    with pytest.raises(ValueError, match="Missing exact SOFR Index"):
        source.realized_factor(anchor, holiday, holiday)
    local, carry = source.project_valuation_carry(holiday, anchor, FlatCurve("2023-05-01", 0.05))
    assert carry == pytest.approx(exp(0.05 / 365))
    assert local.realized_factor(anchor, holiday, holiday) == carry
    assert future not in local.index.index
    assert holiday not in source.index.index


@pytest.mark.parametrize(
    ("tenor", "valuation", "expected"),
    [
        ("1M", "2024-07-31", "2024-08-30"),
        ("3M", "2024-05-31", "2024-08-30"),
        ("6M", "2024-10-18", "2025-04-21"),
        ("1Y", "2024-08-30", "2025-08-29"),
        ("2Y", "2022-08-31", "2024-08-30"),
        ("5Y", "2019-08-30", "2024-08-30"),
    ],
)
def test_scenario_and_export_use_same_adjusted_tenor(tenor, valuation, expected):
    config = load_curve_config()
    dates = tenor_dates(pd.Timestamp(valuation), [tenor], config)
    assert dates[tenor] == pd.Timestamp(expected)
    scenario = build_scenario_curve(valuation, FlatCurve(valuation, 0.04), {tenor: 0.001}, config)
    assert scenario.shock_times[0] == scenario.day_counter.yearFraction(
        to_ql_date(valuation), to_ql_date(expected)
    )
    assert scenario.zero_rate(pd.Timestamp(expected)) == pytest.approx(0.041)
