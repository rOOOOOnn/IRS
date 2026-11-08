"""Value a pay-fixed/receive-compounded-SOFR IRS."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .contract import IRSContract
from .fixed_leg import accrued_fixed, fixed_leg_pv
from .floating_leg import SofrHistory, accrued_floating, floating_leg_pv
from .schedule import AccrualPeriod, build_payment_schedule


@dataclass(frozen=True)
class IRSValuation:
    valuation_date: pd.Timestamp
    pv_fixed: float
    pv_floating: float
    market_value: float
    accrued_fixed: float
    accrued_floating: float
    status: str


def price_irs(
    valuation_date: pd.Timestamp,
    curve: object,
    contract: IRSContract,
    history: SofrHistory,
    periods: list[AccrualPeriod] | None = None,
) -> IRSValuation:
    contract.validate()
    valuation_date = pd.Timestamp(valuation_date).normalize()
    schedule = periods or build_payment_schedule(contract)
    if valuation_date < contract.effective_date:
        raise ValueError("IRS valuation date precedes the contract effective date")
    if valuation_date > schedule[-1].payment_date:
        return IRSValuation(valuation_date, 0.0, 0.0, 0.0, 0.0, 0.0, "MATURED")
    pv_fixed = fixed_leg_pv(valuation_date, curve, contract, schedule)
    pv_floating = floating_leg_pv(valuation_date, curve, history, contract, schedule)
    fixed_accrued = accrued_fixed(valuation_date, contract, schedule)
    floating_accrued = accrued_floating(valuation_date, history, contract, schedule)
    market_value = pv_floating - pv_fixed
    return IRSValuation(
        valuation_date=valuation_date,
        pv_fixed=pv_fixed,
        pv_floating=pv_floating,
        market_value=market_value,
        accrued_fixed=fixed_accrued,
        accrued_floating=floating_accrued,
        status="SUCCESS",
    )
