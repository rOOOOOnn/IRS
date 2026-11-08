"""Daily four-method IRS valuation and selected-method P&L."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from irs_project.curves.bootstrap import build_ois_curve

from .contract import IRSContract
from .fixed_leg import fixed_coupon
from .floating_leg import SofrHistory
from .schedule import AccrualPeriod, build_payment_schedule
from .valuation import price_irs

LOGGER = logging.getLogger(__name__)


def build_daily_valuations(
    market: pd.DataFrame,
    methods: list[str],
    curve_config: dict[str, Any],
    contract: IRSContract,
    history: SofrHistory,
) -> pd.DataFrame:
    periods = build_payment_schedule(contract)
    eligible = market.loc[market["Date"] >= contract.effective_date]
    rows: list[dict[str, Any]] = []
    for sequence, (_, market_row) in enumerate(eligible.iterrows(), start=1):
        valuation_date = pd.Timestamp(market_row["Date"])
        quotes = {
            tenor: float(market_row[column])
            for tenor, column in curve_config["tenors"].items()
            if column in market_row and pd.notna(market_row[column])
        }
        for method in methods:
            record = {
                "Date": valuation_date,
                "Method": method,
                "PV_Fixed": float("nan"),
                "PV_Floating": float("nan"),
                "IRS_Market_Value": float("nan"),
                "Accrued_Fixed": float("nan"),
                "Accrued_Floating": float("nan"),
                "Valuation_Status": "FAILED",
                "Failure_Reason": "",
            }
            try:
                curve = build_ois_curve(valuation_date, quotes, method, curve_config)
                valuation = price_irs(valuation_date, curve, contract, history, periods)
                record.update(
                    {
                        "PV_Fixed": valuation.pv_fixed,
                        "PV_Floating": valuation.pv_floating,
                        "IRS_Market_Value": valuation.market_value,
                        "Accrued_Fixed": valuation.accrued_fixed,
                        "Accrued_Floating": valuation.accrued_floating,
                        "Valuation_Status": valuation.status,
                    }
                )
            except Exception as error:
                record["Failure_Reason"] = str(error)
            rows.append(record)
        if sequence % 100 == 0 or sequence == len(eligible):
            LOGGER.info("IRS pricing progress: %s/%s dates", sequence, len(eligible))
    return pd.DataFrame(rows)


def _realized_net_cashflow(
    previous_date: pd.Timestamp,
    current_date: pd.Timestamp,
    contract: IRSContract,
    history: SofrHistory,
    periods: list[AccrualPeriod],
) -> float:
    net = 0.0
    for period in periods:
        if previous_date < period.payment_date <= current_date:
            floating = contract.notional * (
                history.realized_factor(period.start_date, period.end_date, current_date) - 1.0
            )
            net += floating - fixed_coupon(contract, period)
    return float(net)


def selected_method_pnl(
    valuations: pd.DataFrame,
    selected_method: str,
    contract: IRSContract,
    history: SofrHistory,
) -> pd.DataFrame:
    selected = valuations.loc[
        (valuations["Method"] == selected_method)
        & (valuations["Valuation_Status"].isin(["SUCCESS", "MATURED"]))
    ].copy()
    selected = selected.sort_values("Date").reset_index(drop=True)
    periods = build_payment_schedule(contract)
    cashflows = [0.0]
    for previous, current in zip(selected["Date"][:-1], selected["Date"][1:], strict=True):
        cashflows.append(
            _realized_net_cashflow(
                pd.Timestamp(previous), pd.Timestamp(current), contract, history, periods
            )
        )
    selected["MTM_Change"] = selected["IRS_Market_Value"].diff().fillna(0.0)
    selected["Net_Cashflow"] = cashflows
    selected["Total_PnL"] = selected["MTM_Change"] + selected["Net_Cashflow"]
    selected["Loss"] = -selected["Total_PnL"]
    selected["Cumulative_PnL"] = selected["Total_PnL"].cumsum()
    return selected[
        [
            "Date",
            "IRS_Market_Value",
            "MTM_Change",
            "Net_Cashflow",
            "Total_PnL",
            "Loss",
            "Cumulative_PnL",
            "Valuation_Status",
        ]
    ]
