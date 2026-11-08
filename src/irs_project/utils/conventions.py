"""Map human-readable project conventions to QuantLib objects."""

from __future__ import annotations

from typing import Any

import QuantLib as ql


def calendar_from_name(name: str) -> ql.Calendar:
    calendars = {
        "US_GOVERNMENT_BOND": ql.UnitedStates(ql.UnitedStates.GovernmentBond),
        "US_FEDERAL_RESERVE": ql.UnitedStates(ql.UnitedStates.FederalReserve),
        "WEEKENDS_ONLY": ql.WeekendsOnly(),
    }
    try:
        return calendars[name.upper()]
    except KeyError as error:
        raise ValueError(f"Unsupported calendar: {name}") from error


def day_count_from_name(name: str) -> ql.DayCounter:
    counters: dict[str, ql.DayCounter] = {
        "ACT/360": ql.Actual360(),
        "ACT/365F": ql.Actual365Fixed(),
        "30/360": ql.Thirty360(ql.Thirty360.BondBasis),
    }
    try:
        return counters[name.upper()]
    except KeyError as error:
        raise ValueError(f"Unsupported day-count convention: {name}") from error


def business_day_convention_from_name(name: str) -> int:
    conventions = {
        "FOLLOWING": ql.Following,
        "MODIFIED_FOLLOWING": ql.ModifiedFollowing,
        "PRECEDING": ql.Preceding,
        "UNADJUSTED": ql.Unadjusted,
    }
    try:
        return conventions[name.upper()]
    except KeyError as error:
        raise ValueError(f"Unsupported business-day convention: {name}") from error


def frequency_from_name(name: str) -> int:
    frequencies = {
        "ANNUAL": ql.Annual,
        "SEMIANNUAL": ql.Semiannual,
        "QUARTERLY": ql.Quarterly,
        "MONTHLY": ql.Monthly,
    }
    try:
        return frequencies[name.upper()]
    except KeyError as error:
        raise ValueError(f"Unsupported frequency: {name}") from error


def contract_value(config: dict[str, Any], key: str) -> Any:
    try:
        return config["contract"][key]["value"]
    except KeyError as error:
        raise KeyError(f"Missing contract configuration: {key}") from error
