"""Calibration and curve-shape diagnostics."""

from __future__ import annotations

from typing import Any

import pandas as pd
import QuantLib as ql

from irs_project.utils.conventions import calendar_from_name
from irs_project.utils.dates import from_ql_date, to_ql_date

from .bootstrap import OISCurve


def calibration_frame(curve: OISCurve) -> pd.DataFrame:
    frame = pd.DataFrame(curve.calibration_errors())
    frame.insert(0, "Method", curve.method)
    frame.insert(0, "Date", pd.Timestamp(curve.valuation_date))
    return frame


def forward_shape_diagnostics(curve: OISCurve, step_days: int = 30) -> dict[str, Any]:
    calendar = calendar_from_name(curve.config["curve"]["calendar"])
    start = to_ql_date(curve.valuation_date)
    end = curve.term_structure.maxDate()
    dates: list[ql.Date] = []
    cursor = calendar.advance(start, step_days, ql.Days)
    while cursor < end:
        dates.append(cursor)
        cursor = calendar.advance(cursor, step_days, ql.Days)
    if end > start:
        dates.append(end)
    forwards: list[float] = []
    previous = start
    for current in dates:
        forwards.append(curve.forward_rate(from_ql_date(previous), from_ql_date(current)))
        previous = current
    floor = float(curve.config["curve"]["forward_rate_floor_decimal"])
    cap = float(curve.config["curve"]["forward_rate_cap_decimal"])
    return {
        "Forward_Min": min(forwards) if forwards else float("nan"),
        "Forward_Max": max(forwards) if forwards else float("nan"),
        "Forward_Outside_Config_Bounds": any(value < floor or value > cap for value in forwards),
        "Sample_Count": len(forwards),
    }
