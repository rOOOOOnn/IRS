"""Realized and forecast compounded-SOFR cashflows."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

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

    def project_valuation_carry(
        self, valuation_date: pd.Timestamp, index_date: pd.Timestamp, cutoff_curve: object
    ) -> tuple[SofrHistory, float]:
        """Create a valuation-only history with carry projected from a prior published index."""
        if index_date >= valuation_date or index_date not in self.index.index:
            raise ValueError("SOFR carry requires a published index strictly before valuation")
        index = self.index.loc[:index_date].copy()
        carry = 1.0 / cutoff_curve.discount_factor(valuation_date)
        if not isfinite(carry) or carry <= 0:
            raise ValueError("Invalid projected SOFR carry factor")
        index.loc[valuation_date] = index.loc[index_date] * carry
        return SofrHistory(self.fixings.loc[:index_date], index), carry

    def realized_factor(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        as_of: pd.Timestamp,
    ) -> float:
        if end_date > as_of:
            raise ValueError("Realized SOFR cannot use observations after the valuation date")
        try:
            start_index = float(self.index.at[start_date])
            end_index = float(self.index.at[end_date])
        except KeyError as error:
            raise ValueError(f"Missing exact SOFR Index on {error.args[0].date()}") from error
        if not all(isfinite(value) and value > 0 for value in (start_index, end_index)):
            raise ValueError("SOFR Index values must be finite and positive")
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
