"""Load the configurable research IRS contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from irs_project.utils.conventions import contract_value


@dataclass(frozen=True)
class IRSContract:
    currency: str
    notional: float
    fixed_rate: float
    position: str
    floating_reference: str
    effective_date: pd.Timestamp
    maturity_date: pd.Timestamp
    fixed_payment_frequency: str
    fixed_day_count: str
    floating_day_count: str
    business_day_convention: str
    holiday_calendar: str
    payment_lag_days: int
    observation_lookback_days: int
    observation_shift: bool
    lockout_days: int
    valuation_basis: str

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> IRSContract:
        return cls(
            currency=str(contract_value(config, "currency")),
            notional=float(contract_value(config, "notional")),
            fixed_rate=float(contract_value(config, "fixed_rate_decimal")),
            position=str(contract_value(config, "position")),
            floating_reference=str(contract_value(config, "floating_reference")),
            effective_date=pd.Timestamp(contract_value(config, "effective_date")),
            maturity_date=pd.Timestamp(contract_value(config, "maturity_date")),
            fixed_payment_frequency=str(contract_value(config, "fixed_payment_frequency")),
            fixed_day_count=str(contract_value(config, "fixed_day_count")),
            floating_day_count=str(contract_value(config, "floating_day_count")),
            business_day_convention=str(contract_value(config, "business_day_convention")),
            holiday_calendar=str(contract_value(config, "holiday_calendar")),
            payment_lag_days=int(contract_value(config, "payment_lag_days")),
            observation_lookback_days=int(contract_value(config, "observation_lookback_days")),
            observation_shift=bool(contract_value(config, "observation_shift")),
            lockout_days=int(contract_value(config, "lockout_days")),
            valuation_basis=str(contract_value(config, "valuation_basis")),
        )

    def validate(self) -> None:
        if self.currency != "USD":
            raise ValueError("Only USD contracts are supported")
        if self.notional <= 0:
            raise ValueError("Notional must be positive")
        if self.maturity_date <= self.effective_date:
            raise ValueError("Maturity must be after the effective date")
        if self.position != "PAY_FIXED_RECEIVE_FLOATING":
            raise ValueError("Only pay-fixed/receive-floating is supported in this project")
        if self.floating_reference != "COMPOUNDED_SOFR":
            raise ValueError("Only compounded SOFR is supported")
