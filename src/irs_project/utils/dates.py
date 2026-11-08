"""Cross-platform conversions and date helpers."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import QuantLib as ql

DateLike = date | datetime | pd.Timestamp | str


def to_timestamp(value: DateLike) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def to_ql_date(value: DateLike) -> ql.Date:
    timestamp = to_timestamp(value)
    return ql.Date(timestamp.day, timestamp.month, timestamp.year)


def from_ql_date(value: ql.Date) -> pd.Timestamp:
    return pd.Timestamp(value.year(), value.month(), value.dayOfMonth())


def tenor_to_period(tenor: str) -> ql.Period:
    return ql.Period(tenor)
