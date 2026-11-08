"""Generate adjusted IRS accrual periods and payment dates."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import QuantLib as ql

from irs_project.utils.conventions import (
    business_day_convention_from_name,
    calendar_from_name,
    day_count_from_name,
    frequency_from_name,
)
from irs_project.utils.dates import from_ql_date, to_ql_date

from .contract import IRSContract


@dataclass(frozen=True)
class AccrualPeriod:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    payment_date: pd.Timestamp
    accrual_fraction: float


def build_payment_schedule(contract: IRSContract) -> list[AccrualPeriod]:
    calendar = calendar_from_name(contract.holiday_calendar)
    convention = business_day_convention_from_name(contract.business_day_convention)
    schedule = ql.Schedule(
        to_ql_date(contract.effective_date),
        to_ql_date(contract.maturity_date),
        ql.Period(frequency_from_name(contract.fixed_payment_frequency)),
        calendar,
        convention,
        convention,
        ql.DateGeneration.Backward,
        False,
    )
    day_count = day_count_from_name(contract.fixed_day_count)
    periods = []
    for start, end in zip(list(schedule)[:-1], list(schedule)[1:], strict=True):
        payment = calendar.advance(end, contract.payment_lag_days, ql.Days)
        periods.append(
            AccrualPeriod(
                start_date=from_ql_date(start),
                end_date=from_ql_date(end),
                payment_date=from_ql_date(payment),
                accrual_fraction=float(day_count.yearFraction(start, end)),
            )
        )
    return periods
