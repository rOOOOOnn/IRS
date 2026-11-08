"""Bootstrap daily SOFR OIS curves with a unified query interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import QuantLib as ql

from irs_project.utils.conventions import day_count_from_name
from irs_project.utils.dates import DateLike, from_ql_date, to_ql_date, to_timestamp

from .interpolation import InterpolationMethod, build_piecewise_curve
from .market_instruments import OISInstrumentSet, build_ois_helpers, make_ois_swap


@dataclass
class OISCurve:
    valuation_date: Any
    method: str
    term_structure: Any
    instruments: OISInstrumentSet
    config: dict[str, Any]
    allow_extrapolation: bool = False

    @property
    def max_date(self) -> Any:
        return from_ql_date(self.term_structure.maxDate())

    def _checked_date(self, value: DateLike) -> ql.Date:
        timestamp = to_timestamp(value)
        valuation = to_timestamp(self.valuation_date)
        if timestamp < valuation:
            raise ValueError("Curve queries before the valuation date are not allowed")
        if timestamp > self.max_date and not self.allow_extrapolation:
            raise ValueError(
                f"Maturity {timestamp.date()} exceeds curve maximum {self.max_date.date()}"
            )
        return to_ql_date(timestamp)

    def discount_factor(self, maturity_date: DateLike) -> float:
        ql_date = self._checked_date(maturity_date)
        discount = float(self.term_structure.discount(ql_date))
        if discount <= 0:
            raise ValueError(f"Non-positive discount factor at {maturity_date}: {discount}")
        return discount

    def zero_rate(self, maturity_date: DateLike) -> float:
        ql_date = self._checked_date(maturity_date)
        day_counter = day_count_from_name(self.config["curve"]["reference_day_count"])
        return float(
            self.term_structure.zeroRate(ql_date, day_counter, ql.Continuous, ql.Annual).rate()
        )

    def forward_rate(self, start_date: DateLike, end_date: DateLike) -> float:
        start = self._checked_date(start_date)
        end = self._checked_date(end_date)
        if end <= start:
            raise ValueError("Forward-rate end date must be after the start date")
        day_counter = day_count_from_name(self.config["curve"]["reference_day_count"])
        return float(
            self.term_structure.forwardRate(
                start, end, day_counter, ql.Continuous, ql.Annual
            ).rate()
        )

    def par_ois_rate(self, tenor: str) -> float:
        handle = ql.YieldTermStructureHandle(self.term_structure)
        swap = make_ois_swap(tenor, 0.0, handle, self.config)
        return float(swap.fairRate())

    def calibration_errors(self) -> list[dict[str, Any]]:
        rows = []
        for tenor, helper in zip(self.instruments.tenors, self.instruments.helpers, strict=True):
            model_quote = float(helper.impliedQuote())
            market_quote = float(self.instruments.market_quotes[tenor])
            rows.append(
                {
                    "Tenor": tenor,
                    "Market_Quote": market_quote,
                    "Model_Quote": model_quote,
                    "Error_bps": (model_quote - market_quote) * 10_000,
                }
            )
        return rows


def build_ois_curve(
    valuation_date: DateLike,
    market_quotes: dict[str, float],
    method: str | InterpolationMethod,
    config: dict[str, Any],
    *,
    enforce_required_tenors: bool = True,
    allow_extrapolation: bool | None = None,
) -> OISCurve:
    if enforce_required_tenors:
        required = set(config["required_pricing_tenors"])
        missing = sorted(required - set(market_quotes))
        if missing:
            raise ValueError(f"Missing required curve tenors: {missing}")
    if len(market_quotes) < 3:
        raise ValueError("At least three market tenors are required to build a curve")
    ql_date = to_ql_date(valuation_date)
    ql.Settings.instance().evaluationDate = ql_date
    instruments = build_ois_helpers(market_quotes, config)
    day_counter = day_count_from_name(config["curve"]["reference_day_count"])
    term_structure = build_piecewise_curve(method, ql_date, instruments.helpers, day_counter)
    extrapolate = (
        bool(config["curve"]["allow_extrapolation"])
        if allow_extrapolation is None
        else allow_extrapolation
    )
    if extrapolate:
        term_structure.enableExtrapolation()
    term_structure.discount(term_structure.maxDate())
    return OISCurve(
        valuation_date=to_timestamp(valuation_date),
        method=str(InterpolationMethod(method)),
        term_structure=term_structure,
        instruments=instruments,
        config=config,
        allow_extrapolation=extrapolate,
    )
