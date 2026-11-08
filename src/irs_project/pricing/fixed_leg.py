"""Fixed-leg cashflows, PV, and accrued interest."""

from __future__ import annotations

import pandas as pd

from irs_project.utils.conventions import day_count_from_name
from irs_project.utils.dates import to_ql_date

from .contract import IRSContract
from .schedule import AccrualPeriod


def fixed_coupon(contract: IRSContract, period: AccrualPeriod) -> float:
    return contract.notional * contract.fixed_rate * period.accrual_fraction


def fixed_leg_pv(
    valuation_date: pd.Timestamp,
    curve: object,
    contract: IRSContract,
    periods: list[AccrualPeriod],
) -> float:
    return float(
        sum(
            fixed_coupon(contract, period) * curve.discount_factor(period.payment_date)
            for period in periods
            if period.payment_date > valuation_date
        )
    )


def accrued_fixed(
    valuation_date: pd.Timestamp,
    contract: IRSContract,
    periods: list[AccrualPeriod],
) -> float:
    day_count = day_count_from_name(contract.fixed_day_count)
    for period in periods:
        if period.start_date < valuation_date < period.end_date:
            fraction = day_count.yearFraction(
                to_ql_date(period.start_date), to_ql_date(valuation_date)
            )
            return float(contract.notional * contract.fixed_rate * fraction)
    return 0.0
