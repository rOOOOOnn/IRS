"""Apply tenor shocks to a base zero curve and reprice the IRS."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Any

import numpy as np
import pandas as pd
import QuantLib as ql

from irs_project.utils.conventions import day_count_from_name
from irs_project.utils.dates import DateLike, tenor_to_period, to_ql_date, to_timestamp

from .contract import IRSContract
from .floating_leg import SofrHistory
from .valuation import IRSValuation, price_irs


@dataclass
class ScenarioCurve:
    valuation_date: pd.Timestamp
    base_curve: Any
    shock_times: np.ndarray
    shocks: np.ndarray
    day_counter: ql.DayCounter

    def _time(self, value: DateLike) -> float:
        date = to_ql_date(value)
        return float(self.day_counter.yearFraction(to_ql_date(self.valuation_date), date))

    def _shock(self, value: DateLike) -> float:
        time = self._time(value)
        return float(np.interp(time, self.shock_times, self.shocks))

    def zero_rate(self, maturity_date: DateLike) -> float:
        return float(self.base_curve.zero_rate(maturity_date) + self._shock(maturity_date))

    def discount_factor(self, maturity_date: DateLike) -> float:
        time = self._time(maturity_date)
        discount = float(
            self.base_curve.discount_factor(maturity_date) * exp(-self._shock(maturity_date) * time)
        )
        if discount <= 0:
            raise ValueError("Scenario discount factor must be positive")
        return discount

    def forward_rate(self, start_date: DateLike, end_date: DateLike) -> float:
        start_time = self._time(start_date)
        end_time = self._time(end_date)
        if end_time <= start_time:
            raise ValueError("Forward-rate end date must be after the start date")
        start_df = self.discount_factor(start_date)
        end_df = self.discount_factor(end_date)
        return float(-log(end_df / start_df) / (end_time - start_time))


def build_scenario_curve(
    valuation_date: DateLike,
    base_curve: Any,
    zero_rate_shocks: dict[str, float],
    curve_config: dict[str, Any],
) -> ScenarioCurve:
    if not zero_rate_shocks:
        raise ValueError("At least one zero-rate shock is required")
    valuation = to_timestamp(valuation_date)
    day_counter = day_count_from_name(curve_config["curve"]["reference_day_count"])
    valuation_ql = to_ql_date(valuation)
    pairs = []
    for tenor, shock in zero_rate_shocks.items():
        maturity = valuation_ql + tenor_to_period(tenor)
        time = day_counter.yearFraction(valuation_ql, maturity)
        pairs.append((float(time), float(shock)))
    pairs.sort()
    return ScenarioCurve(
        valuation_date=valuation,
        base_curve=base_curve,
        shock_times=np.array([item[0] for item in pairs]),
        shocks=np.array([item[1] for item in pairs]),
        day_counter=day_counter,
    )


def scenario_irs_value(
    valuation_date: DateLike,
    base_curve: Any,
    zero_rate_shocks: dict[str, float],
    curve_config: dict[str, Any],
    contract: IRSContract,
    history: SofrHistory,
) -> tuple[IRSValuation, float]:
    base = price_irs(to_timestamp(valuation_date), base_curve, contract, history)
    scenario_curve = build_scenario_curve(
        valuation_date, base_curve, zero_rate_shocks, curve_config
    )
    scenario = price_irs(to_timestamp(valuation_date), scenario_curve, contract, history)
    return scenario, scenario.market_value - base.market_value
