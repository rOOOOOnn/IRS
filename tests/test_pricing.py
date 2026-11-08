from __future__ import annotations

from math import exp, log

import pandas as pd
import pytest

from irs_project.data.load_market_data import load_contract_config, load_curve_config
from irs_project.pricing.contract import IRSContract
from irs_project.pricing.floating_leg import SofrHistory
from irs_project.pricing.scenario_repricing import build_scenario_curve
from irs_project.pricing.schedule import build_payment_schedule
from irs_project.pricing.valuation import price_irs


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


def test_contract_schedule_has_five_annual_periods() -> None:
    periods = build_payment_schedule(_contract())
    assert len(periods) == 5
    assert periods[0].start_date == pd.Timestamp("2023-05-01")


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
