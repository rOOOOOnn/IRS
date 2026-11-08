"""Construct consistently configured SOFR OIS helpers and swaps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import QuantLib as ql

from irs_project.utils.conventions import (
    business_day_convention_from_name,
    calendar_from_name,
    day_count_from_name,
    frequency_from_name,
)
from irs_project.utils.dates import tenor_to_period


@dataclass(frozen=True)
class OISInstrumentSet:
    helpers: list[ql.OISRateHelper]
    market_quotes: dict[str, float]
    tenors: list[str]


def make_sofr_index(curve_handle: ql.YieldTermStructureHandle | None = None) -> ql.Sofr:
    return ql.Sofr(curve_handle or ql.YieldTermStructureHandle())


def build_ois_helpers(
    market_quotes: dict[str, float],
    config: dict[str, Any],
) -> OISInstrumentSet:
    curve_config = config["curve"]
    calendar = calendar_from_name(curve_config["calendar"])
    payment_calendar = calendar_from_name(curve_config["calendar"])
    payment_convention = business_day_convention_from_name(curve_config["payment_convention"])
    convention = business_day_convention_from_name(curve_config["business_day_convention"])
    payment_frequency = frequency_from_name(curve_config["fixed_leg_frequency"])
    fixed_day_count = day_count_from_name(curve_config["fixed_leg_day_count"])
    index = make_sofr_index()
    ordered_tenors = [tenor for tenor in config["tenors"] if tenor in market_quotes]
    helpers: list[ql.OISRateHelper] = []
    for tenor in ordered_tenors:
        helper = ql.OISRateHelper(
            int(curve_config["settlement_days"]),
            tenor_to_period(tenor),
            ql.QuoteHandle(ql.SimpleQuote(float(market_quotes[tenor]))),
            index,
            telescopicValueDates=bool(curve_config["telescopic_value_dates"]),
            paymentLag=int(curve_config["payment_lag_days"]),
            paymentConvention=payment_convention,
            paymentFrequency=payment_frequency,
            paymentCalendar=payment_calendar,
            averagingMethod=ql.RateAveraging.Compound,
            fixedPaymentFrequency=payment_frequency,
            fixedCalendar=calendar,
            lookbackDays=int(curve_config["lookback_days"]),
            lockoutDays=int(curve_config["lockout_days"]),
            applyObservationShift=bool(curve_config["observation_shift"]),
            rule=ql.DateGeneration.Backward,
            overnightCalendar=calendar,
            convention=convention,
            fixedDayCount=fixed_day_count,
        )
        helpers.append(helper)
    return OISInstrumentSet(helpers=helpers, market_quotes=market_quotes, tenors=ordered_tenors)


def make_ois_swap(
    tenor: str,
    fixed_rate: float,
    curve_handle: ql.YieldTermStructureHandle,
    config: dict[str, Any],
    nominal: float = 1.0,
) -> ql.OvernightIndexedSwap:
    curve_config = config["curve"]
    calendar = calendar_from_name(curve_config["calendar"])
    convention = business_day_convention_from_name(curve_config["business_day_convention"])
    payment_convention = business_day_convention_from_name(curve_config["payment_convention"])
    evaluation_date = ql.Settings.instance().evaluationDate
    start = calendar.advance(evaluation_date, int(curve_config["settlement_days"]), ql.Days)
    maturity = calendar.advance(start, tenor_to_period(tenor), convention)
    schedule = ql.Schedule(
        start,
        maturity,
        ql.Period(frequency_from_name(curve_config["fixed_leg_frequency"])),
        calendar,
        convention,
        convention,
        ql.DateGeneration.Backward,
        False,
    )
    index = make_sofr_index(curve_handle)
    swap = ql.OvernightIndexedSwap(
        ql.OvernightIndexedSwap.Payer,
        nominal,
        schedule,
        fixed_rate,
        day_count_from_name(curve_config["fixed_leg_day_count"]),
        index,
        0.0,
        int(curve_config["payment_lag_days"]),
        payment_convention,
        calendar,
        bool(curve_config["telescopic_value_dates"]),
        ql.RateAveraging.Compound,
        int(curve_config["lookback_days"]),
        int(curve_config["lockout_days"]),
        bool(curve_config["observation_shift"]),
    )
    swap.setPricingEngine(ql.DiscountingSwapEngine(curve_handle))
    return swap
