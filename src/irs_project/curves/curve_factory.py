"""High-level factory for one valuation-date curve."""

from __future__ import annotations

from typing import Any

import pandas as pd

from irs_project.data.load_market_data import quotes_for_date

from .bootstrap import OISCurve, build_ois_curve


def curve_from_market_row(
    market_frame: pd.DataFrame,
    valuation_date: pd.Timestamp,
    method: str,
    config: dict[str, Any],
) -> OISCurve:
    quotes = quotes_for_date(market_frame, valuation_date, config["tenors"])
    return build_ois_curve(valuation_date, quotes, method, config)
