
import numpy as np
import pandas as pd
import pytest

from irs_project.backtesting.backtest import (
    kupiec_test,
    christoffersen_test
)

from irs_project.backtesting.es_calibration import (
    es_identification,
    bootstrap_es_ci
)

from irs_project.backtesting.reporting import (
    common_dates,
    coverage,
    validate_and_scope
)


def test_kupiec_no_exceedances():
    result = kupiec_test(
        np.zeros(100, dtype=int),
        0.95
    )

    assert np.isfinite(result["LR_UC"])
    assert 0 <= result["p_UC"] <= 1


def test_kupiec_expected_exception_rate():
    exceptions = [1] * 5 + [0] * 95

    result = kupiec_test(
        exceptions,
        0.95
    )

    assert result["LR_UC"] == pytest.approx(
        0, abs=1e-12
    )


def test_es_identification():

    residuals = es_identification(
        loss=[20, 0],
        var=[10, 10],
        es=[15, 15],
        confidence=0.95
    )

    assert residuals.tolist() == pytest.approx(
        [195, -5]
    )


def test_es_invalid_input():

    with pytest.raises(ValueError):
        es_identification(
            loss=[1],
            var=[3],
            es=[2],
            confidence=0.95
        )


def test_christoffersen_no_gap_crossing():

    dates = pd.to_datetime([
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
        "2026-01-08"
    ])

    group = pd.DataFrame({
        "Date": dates,
        "Forecast_As_Of": pd.to_datetime([
            "2026-01-02",
            "2026-01-05",
            "2026-01-06",
            "2026-01-07"
        ]),
        "Valid": [True, True, False, True],
        "Exception": [0, 1, np.nan, 1]
    })

    result = christoffersen_test(group)

    assert result["Transitions"] == 1
    assert result["n01"] == 1
    assert result["n11"] == 0


def test_common_sample_requires_all_models():

    rows = []

    for date in ["2026-01-05", "2026-01-06"]:
        for model in ("HS", "EWMA", "PCA_MC"):
            for level in (0.95, 0.99):

                valid = not (
                    date == "2026-01-06"
                    and model == "HS"
                )

                rows.append({
                    "Date": pd.Timestamp(date),
                    "Model": model,
                    "Confidence_Level": level,
                    "Valid": valid
                })

    df = pd.DataFrame(rows)

    common = common_dates(df)
    result = coverage(df, common)

    assert result == {
        "Candidate_Dates": 2,
        "Common_Valid_Dates": 1,
        "Failed_Dates": 1
    }


def test_es_bootstrap_handles_gaps():

    dates = pd.bdate_range(
        "2026-01-05",
        periods=55
    )

    forecast_dates = [
        dates[0] - pd.Timedelta(days=3),
        *dates[:-1]
    ]

    group = pd.DataFrame({
        "Date": dates,
        "Forecast_As_Of": forecast_dates,
        "Valid": [True] * 55,
        "Loss": [0.0] * 55,
        "VaR": [10.0] * 55,
        "ES": [15.0] * 55
    })

    group.loc[17, "Valid"] = False

    result = bootstrap_es_ci(
        group,
        0.95,
        simulations=100
    )

    assert result["ES_Segment_Count"] == 2

    assert np.isfinite(
        result["ES_CI_Lower"]
    )


def test_information_cutoff_rejects_lookahead():

    date = pd.Timestamp("2026-01-06")

    df = pd.DataFrame({
        "Date": [date],
        "Model": ["HS"],
        "Confidence_Level": [0.95],
        "Forecast_As_Of": [date],
        "PnL_Previous_Date": [
            pd.Timestamp("2026-01-05")
        ],
        "Loss": [1.0],
        "VaR": [2.0],
        "ES": [3.0],
        "Valid": [True],
        "Exception": [0.0]
    })

    alignment = pd.DataFrame({
        "Date": [date],
        "Information_Cutoff": [date]
    })

    diagnostics = pd.DataFrame({
        "Date": [date],
        "Model": ["HS"],
        "Status": ["SUCCESS"],
        "Reason": [""]
    })

    config = {
        "splits": {
            "test": {
                "start": "2023-05-31",
                "end": None
            }
        }
    }

    result = validate_and_scope(
        df,
        alignment,
        diagnostics,
        config
    )

    assert not bool(result.loc[0, "Valid"])

    assert (
        result.loc[0, "Invalid_Reason"]
        == "TIME_ALIGNMENT"
    )


def test_duplicate_diagnostics_rejected():

    date = pd.Timestamp("2026-01-06")
    previous = pd.Timestamp("2026-01-05")

    df = pd.DataFrame({
        "Date": [date],
        "Model": ["HS"],
        "Confidence_Level": [0.95],
        "Forecast_As_Of": [previous],
        "PnL_Previous_Date": [previous],
        "Loss": [1.0],
        "VaR": [2.0],
        "ES": [3.0],
        "Valid": [True],
        "Exception": [0.0]
    })

    alignment = pd.DataFrame({
        "Date": [date],
        "Information_Cutoff": [previous]
    })

    diagnostics = pd.DataFrame({
        "Date": [date, date],
        "Model": ["HS", "HS"],
        "Status": ["SUCCESS", "SUCCESS"],
        "Reason": ["", ""]
    })

    config = {
        "splits": {
            "test": {
                "start": "2023-05-31",
                "end": None
            }
        }
    }

    with pytest.raises(ValueError, match="Duplicate"):
        validate_and_scope(
            df,
            alignment,
            diagnostics,
            config
        )
