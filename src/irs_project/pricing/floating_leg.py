"""Realized and forecast compounded-SOFR cashflows."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .contract import IRSContract
from .schedule import AccrualPeriod


@dataclass
class SofrHistory:
    fixings: pd.Series
    index: pd.Series

    @classmethod
    def from_frames(cls, fixings: pd.DataFrame, index: pd.DataFrame) -> SofrHistory:
        fixing_series = fixings.set_index("Date")["SOFR_Decimal"].sort_index()
        index_series = index.set_index("Date")["SOFR_Index"].sort_index()
        return cls(fixings=fixing_series, index=index_series)

    def _value_on_or_before(
        self, series: pd.Series, target: pd.Timestamp, as_of: pd.Timestamp
    ) -> tuple[pd.Timestamp, float]:
        eligible = series.loc[(series.index <= target) & (series.index <= as_of)]
        if eligible.empty:
            raise ValueError(f"No SOFR history available on or before {target.date()}")
        return pd.Timestamp(eligible.index[-1]), float(eligible.iloc[-1])

    def realized_factor(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        as_of: pd.Timestamp,
    ) -> float:
        if end_date > as_of:
            raise ValueError("Realized SOFR cannot use observations after the valuation date")
        _, start_index = self._value_on_or_before(self.index, start_date, as_of)
        _, end_index = self._value_on_or_before(self.index, end_date, as_of)
        if start_index <= 0 or end_index <= 0:
            raise ValueError("SOFR Index values must be positive")
        return end_index / start_index


def compounded_factor(
    valuation_date: pd.Timestamp,
    curve: object,
    history: SofrHistory,
    period: AccrualPeriod,
) -> float:
    if period.end_date <= valuation_date:
        return history.realized_factor(period.start_date, period.end_date, valuation_date)
    if period.start_date >= valuation_date:
        return curve.discount_factor(period.start_date) / curve.discount_factor(period.end_date)
    realized = history.realized_factor(period.start_date, valuation_date, valuation_date)
    forecast = 1.0 / curve.discount_factor(period.end_date)
    return realized * forecast


def floating_coupon(
    valuation_date: pd.Timestamp,
    curve: object,
    history: SofrHistory,
    contract: IRSContract,
    period: AccrualPeriod,
) -> float:
    return contract.notional * (compounded_factor(valuation_date, curve, history, period) - 1.0)


def floating_leg_pv(
    valuation_date: pd.Timestamp,
    curve: object,
    history: SofrHistory,
    contract: IRSContract,
    periods: list[AccrualPeriod],
) -> float:
    return float(
        sum(
            floating_coupon(valuation_date, curve, history, contract, period)
            * curve.discount_factor(period.payment_date)
            for period in periods
            if period.payment_date > valuation_date
        )
    )


def accrued_floating(
    valuation_date: pd.Timestamp,
    history: SofrHistory,
    contract: IRSContract,
    periods: list[AccrualPeriod],
) -> float:
    for period in periods:
        if period.start_date < valuation_date < period.end_date:
            factor = history.realized_factor(period.start_date, valuation_date, valuation_date)
            return float(contract.notional * (factor - 1.0))
    return 0.0
