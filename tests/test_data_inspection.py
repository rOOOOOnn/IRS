from pathlib import Path

import pandas as pd

from irs_project.data.inspect import resolve_series

CONFIG = {
    "series": {
        "USOSFR1": {"aliases": ["USOSFR1"], "kind": "OIS_PAR_RATE", "tenor": "1Y"},
        "USOSFR10": {"aliases": ["USOSFR10"], "kind": "OIS_PAR_RATE", "tenor": "10Y"},
    }
}


def test_resolve_series_does_not_confuse_one_year_and_ten_year() -> None:
    ticker, _ = resolve_series(Path("USOSFR10.xlsx"), {"Security": "USOSFR10 BGN Curncy"}, CONFIG)
    assert ticker == "USOSFR10"


def test_resolve_series_uses_security_metadata_for_neutral_filename() -> None:
    ticker, _ = resolve_series(Path("download.xlsx"), {"Security": "USOSFR1 BGN Curncy"}, CONFIG)
    assert ticker == "USOSFR1"


def test_dates_are_normalizable() -> None:
    dates = pd.to_datetime(["2023-05-01 12:00", "2023-05-02 08:00"]).normalize()
    assert dates[0] == pd.Timestamp("2023-05-01")
