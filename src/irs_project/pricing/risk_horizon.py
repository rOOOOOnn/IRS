"""Shared cashflow-aware holding-period repricing, with no future SOFR observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .contract import IRSContract
from .daily_mtm import _realized_net_cashflow
from .floating_leg import SofrHistory
from .scenario_repricing import ScenarioCurve, build_scenario_curve
from .schedule import build_payment_schedule
from .valuation import discounted_leg_values, price_irs


@dataclass
class RolledCurve:
    """Forward discount ratios from an already-built cutoff-date curve."""

    valuation_date: pd.Timestamp
    base_curve: Any

    def discount_factor(self, date: Any) -> float:
        if pd.Timestamp(date) < self.valuation_date:
            raise ValueError("Rolled curve query before the horizon date")
        return self.base_curve.discount_factor(date) / self.base_curve.discount_factor(
            self.valuation_date
        )


@dataclass
class BatchScenarioCurve(ScenarioCurve):
    """Same interpolation/discounting as ScenarioCurve, evaluated for many shock vectors."""

    def _shock(self, value: Any) -> np.ndarray:
        time = self._time(value)
        weights = np.array(
            [np.interp(time, self.shock_times, basis) for basis in np.eye(len(self.shock_times))]
        )
        return self.shocks @ weights

    def discount_factor(self, date: Any) -> np.ndarray:
        time = self._time(date)
        result = self.base_curve.discount_factor(date) * np.exp(-self._shock(date) * time)
        if not np.isfinite(result).all() or np.any(result <= 0):
            raise ValueError("Invalid scenario discount factors; no scenarios were dropped")
        return result


def cutoff_history(history: SofrHistory, cutoff: pd.Timestamp) -> SofrHistory:
    """Physically remove future records, including observations the engine could otherwise see."""
    return SofrHistory(
        fixings=history.fixings.loc[:cutoff].copy(),
        index=history.index.loc[:cutoff].copy(),
    )


def projected_history(
    history: SofrHistory, cutoff: pd.Timestamp, target: pd.Timestamp, curve: Any
) -> SofrHistory:
    """Project unpublished SOFR Index from the cutoff curve, NOT from realized future data.

    This deterministic carry assumption is explicit and common to all three risk models.
    Index dated t is assumed available at the end of t, as in the main pricing pipeline.
    """
    known = cutoff_history(history, cutoff)
    if cutoff not in known.index.index:
        raise ValueError("Missing exact cutoff SOFR Index; refusing stale forward filling")
    if not np.isfinite(known.index.to_numpy()).all() or (known.index <= 0).any():
        raise ValueError("Invalid known SOFR Index")
    future_dates = pd.date_range(cutoff + pd.Timedelta(days=1), target, freq="D")
    projected = pd.Series(
        [float(known.index.loc[cutoff]) / curve.discount_factor(d) for d in future_dates],
        index=future_dates,
        dtype=float,
    )
    return SofrHistory(known.fixings, pd.concat([known.index, projected]))


class HorizonRepricer:
    """Price end-of-horizon remaining cashflows plus cashflows settled during (t,u]."""

    def __init__(self, cutoff, target, curve, config, contract: IRSContract, history):
        self.cutoff, self.target = pd.Timestamp(cutoff), pd.Timestamp(target)
        if self.target <= self.cutoff:
            raise ValueError("Target must follow information cutoff")
        self.config, self.contract = config, contract
        self.tenors = list(config["required_pricing_tenors"])
        self.periods = build_payment_schedule(contract)
        known = cutoff_history(history, self.cutoff)
        if self.cutoff not in known.index.index:
            raise ValueError("Missing exact cutoff SOFR Index; refusing stale forward filling")
        required_index_dates = {self.cutoff}
        for period in self.periods:
            if period.payment_date > self.cutoff:
                for date in (period.start_date, period.end_date):
                    if date <= self.cutoff:
                        required_index_dates.add(date)
        missing_dates = sorted(required_index_dates - set(known.index.index))
        if missing_dates:
            raise ValueError(f"Missing historical SOFR Index boundaries: {missing_dates}")
        self.base = price_irs(self.cutoff, curve, contract, known, self.periods)
        zero = {tenor: 0.0 for tenor in self.tenors}
        # Same-date zero-shock comparison with the existing scenario module.
        self.same_date_zero = price_irs(
            self.cutoff,
            build_scenario_curve(self.cutoff, curve, zero, config),
            contract,
            known,
            self.periods,
        )
        self.zero_error = abs(self.same_date_zero.market_value - self.base.market_value)
        if self.zero_error > 1e-6:
            raise ValueError(f"Zero-shock pricing mismatch: {self.zero_error}")
        self.history = projected_history(history, self.cutoff, self.target, curve)
        self.rolled = RolledCurve(self.target, curve)
        self.cashflow = _realized_net_cashflow(
            self.cutoff, self.target, contract, self.history, self.periods
        )
        self.template = build_scenario_curve(self.target, self.rolled, zero, config)
        self.zero_horizon = price_irs(
            self.target, self.template, contract, self.history, self.periods
        ).market_value
        self.shock_order = np.argsort(
            [
                build_scenario_curve(self.target, self.rolled, {t: 0.0}, self.config).shock_times[0]
                for t in self.tenors
            ]
        )
        batch_zero = self.values(np.zeros((1, len(self.tenors))))[0]
        if abs(batch_zero - self.zero_horizon) > 1e-6:
            raise ValueError("Batch/scalar zero-shock horizon values disagree")
        self.zero_horizon_error = abs(batch_zero - self.zero_horizon)

    def values(self, shocks: np.ndarray) -> np.ndarray:
        shocks = np.atleast_2d(np.asarray(shocks, dtype=float))
        if shocks.shape[1] != len(self.tenors) or not np.isfinite(shocks).all():
            raise ValueError("Invalid scenario shock matrix")
        # Align matrix columns with the existing module's sorted shock times.
        curve = BatchScenarioCurve(
            self.target,
            self.rolled,
            self.template.shock_times,
            shocks[:, self.shock_order],
            self.template.day_counter,
        )
        # Both price_irs and batch repricing call this same cashflow-pricing kernel.
        fixed, floating = discounted_leg_values(
            self.target, curve, self.contract, self.history, self.periods
        )
        values = np.broadcast_to(np.asarray(floating - fixed), (len(shocks),)).copy()
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite scenario values; entire model forecast is rejected")
        return values

    def losses(self, shocks: np.ndarray) -> np.ndarray:
        return self.base.market_value - self.values(shocks) - self.cashflow
