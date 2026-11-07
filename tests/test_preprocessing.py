import pandas as pd

from irs_project.data.merge import (
    ALL_TENOR_COLUMNS,
    apply_five_year_curve_policy,
    assign_split,
    ois_long_to_wide,
)
from irs_project.data.preprocess import infer_rate_decimal, robust_jump_mask

SPLITS = {
    "training": {"start": "2018-04-02", "end": "2021-12-31"},
    "validation": {"start": "2022-01-03", "end": "2023-04-28"},
    "inception_transition": {"start": "2023-05-01", "end": "2023-05-30"},
    "test": {"start": "2023-05-31", "end": None},
}


def test_percent_values_are_converted_to_decimal() -> None:
    converted, flag = infer_rate_decimal(pd.Series([3.5, 4.0, 4.5]))
    assert flag == "UNIT_INFERRED_PERCENT"
    assert converted.tolist() == [0.035, 0.04, 0.045]


def test_chronological_split_boundaries() -> None:
    dates = pd.Series(pd.to_datetime(["2021-12-31", "2022-01-03", "2023-05-01", "2023-05-31"]))
    assert assign_split(dates, SPLITS).tolist() == [
        "TRAINING",
        "VALIDATION",
        "INCEPTION_TRANSITION",
        "TEST",
    ]


def test_pre_sofr_dates_do_not_enter_main_wide_sample() -> None:
    long = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2017-01-03", "2018-04-02", "2018-04-02"]),
            "Ticker": ["USOSFRA", "USOSFRA", "USOSFRC"],
            "Tenor": ["1M", "1M", "3M"],
            "Rate_Decimal": [0.01, 0.02, 0.021],
        }
    )
    wide = ois_long_to_wide(long, pd.Timestamp("2018-04-02"))
    assert wide["Date"].min() == pd.Timestamp("2018-04-02")
    assert wide.loc[0, "OIS_1M"] == 0.02


def test_robust_jump_detection_flags_large_change() -> None:
    values = pd.Series([4.00, 4.01, 4.02, 4.80, 4.81])
    mask = robust_jump_mask(values)
    assert bool(mask.iloc[3])


def test_five_year_policy_keeps_optional_gap_and_drops_required_gap() -> None:
    wide = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05"]),
            **{column: [0.01, 0.02, 0.03] for column in ALL_TENOR_COLUMNS},
        }
    )
    wide.loc[1, "OIS_7Y"] = float("nan")
    wide.loc[2, "OIS_5Y"] = float("nan")

    curve_inputs, incomplete, by_tenor = apply_five_year_curve_policy(wide, SPLITS)

    assert curve_inputs["Date"].tolist() == [
        pd.Timestamp("2022-01-03"),
        pd.Timestamp("2022-01-04"),
    ]
    assert incomplete.loc[0, "Missing_Required_Tenors"] == "5Y"
    assert incomplete.loc[0, "Treatment"] == "DROPPED_FROM_COMPLETE_CURVE_PANEL"
    assert by_tenor.set_index("Tenor").loc["7Y", "Missing_Dates"] == 1
