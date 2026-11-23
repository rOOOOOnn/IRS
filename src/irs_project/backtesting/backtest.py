
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import xlogy
from scipy.stats import chi2

# Project root: IRS/
ROOT = Path(__file__).resolve().parents[3]

TEST_START = pd.Timestamp("2023-05-31")
MODELS = ("HS", "EWMA", "PCA_MC")


def read_inputs():
    """Load forecasts, realized P&L and alignment audit."""
    paths = {
        "pnl": ROOT / "outputs/pricing/irs_mtm_pnl.csv",
        "risk": ROOT / "outputs/risk/risk_model_outputs.csv",
        "alignment": ROOT / "outputs/risk/risk_pnl_alignment.csv",
    }

    for name, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {name} input: {path}"
            )

    pnl = pd.read_csv(paths["pnl"], parse_dates=["Date"])
    risk = pd.read_csv(
        paths["risk"],
        parse_dates=["Date", "Forecast_As_Of"],
    )
    alignment = pd.read_csv(
        paths["alignment"], parse_dates=["Date"]
    )

    return pnl, risk, alignment

def prepare_data(pnl, risk, alignment):
    """Align forecasts to next-observation realized loss."""

    required_pnl = {
        "Date", "Total_PnL", "Loss",
        "Valuation_Status",
    }
    required_risk = {
        "Date", "Model", "Confidence_Level",
        "Forecast_Horizon", "Forecast_As_Of",
        "VaR", "ES",
    }
    required_alignment = {
        "Date", "Alignment_Status",
        "PnL_Previous_Date", "Realized_Loss",
    }

    for name, data, columns in (
        ("P&L", pnl, required_pnl),
        ("Risk", risk, required_risk),
        ("Alignment", alignment, required_alignment),
    ):
        missing = columns - set(data.columns)
        if missing:
            raise ValueError(
                f"{name} missing columns: {sorted(missing)}"
            )

    pnl = pnl.sort_values("Date").copy()

    if pnl["Date"].duplicated().any():
        raise ValueError("Duplicate P&L dates")

    if alignment["Date"].duplicated().any():
        raise ValueError("Duplicate alignment dates")

    risk_key = ["Date", "Model", "Confidence_Level"]
    if risk.duplicated(risk_key).any():
        raise ValueError("Duplicate risk forecast keys")

    pnl["Previous_Date"] = pnl["Date"].shift()

    alignment = alignment.copy()
    alignment["PnL_Previous_Date"] = pd.to_datetime(
        alignment["PnL_Previous_Date"]
    )

    df = risk.merge(
        pnl[
            [
                "Date", "Loss", "Total_PnL",
                "Valuation_Status", "Previous_Date",
            ]
        ],
        on="Date",
        how="left",
        validate="many_to_one",
    )

    df = df.merge(
        alignment[
            [
                "Date", "Alignment_Status",
                "PnL_Previous_Date", "Realized_Loss",
            ]
        ],
        on="Date",
        how="left",
        validate="many_to_one",
    )

    # Restrict to the specified out-of-sample period.
    df = df[df["Date"] >= TEST_START].copy()

    # Convert to numeric values.
    for col in (
        "Confidence_Level", "VaR", "ES",
        "Loss", "Total_PnL", "Realized_Loss",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df.empty:
        raise ValueError("No test-period forecasts found")

    # Check that realized Loss = -Total_PnL.
    pnl_consistent = np.isclose(
        df["Loss"],
        -df["Total_PnL"],
        atol=1e-6,
        rtol=0,
    )

    alignment_consistent = np.isclose(
        df["Loss"],
        df["Realized_Loss"],
        atol=1e-6,
        rtol=0,
    )

    finite = np.isfinite(
        df[["VaR", "ES", "Loss", "Total_PnL"]]
    ).all(axis=1)

    # A usable forecast must satisfy all checks.
    df["Valid"] = (
        finite
        & df["Model"].isin(MODELS)
        & df["Confidence_Level"].isin([0.95, 0.99])
        & df["Forecast_Horizon"].eq("1D")
        & df["VaR"].ge(0)
        & df["ES"].ge(df["VaR"])
        & df["Valuation_Status"].isin(
            ["SUCCESS", "MATURED"]
        )
        & df["Alignment_Status"].eq("MATCHED")
        & df["Forecast_As_Of"].eq(df["Previous_Date"])
        & df["Forecast_As_Of"].eq(
            df["PnL_Previous_Date"]
        )
        & pnl_consistent
        & alignment_consistent
    )

    # Missing/invalid observations are not exceptions.
    # Preserve them as NaN, rather than treating as zero.
    df["Exception"] = np.where(
        df["Valid"],
        (df["Loss"] > df["VaR"]).astype(float),
        np.nan,
    )

    return df.sort_values(
        ["Confidence_Level", "Model", "Date"]
    ).reset_index(drop=True)

def kupiec_test(exceptions, confidence):
    """Kupiec unconditional coverage / POF test."""
    x = np.asarray(exceptions, dtype=int)

    n = len(x)
    if n == 0:
        return {
            "LR_UC": np.nan,
            "p_UC": np.nan,
        }

    failures = int(x.sum())

    p0 = 1.0 - confidence
    phat = failures / n

    # Log likelihood under the null hypothesis.
    ll_null = (
        xlogy(failures, p0)
        + xlogy(n - failures, 1 - p0)
    )

    # Log likelihood under the alternative.
    ll_alt = (
        xlogy(failures, phat)
        + xlogy(n - failures, 1 - phat)
    )

    lr = max(0.0, 2.0 * (ll_alt - ll_null))
    p_value = chi2.sf(lr, df=1)

    return {
        "LR_UC": float(lr),
        "p_UC": float(p_value),
    }

def christoffersen_test(group):
    """Christoffersen first-order independence test.

    Only consecutive valid forecast intervals are used.
    Sparse exceptions are reported as insufficient data.
    """
    group = group.sort_values("Date").reset_index(drop=True)

    previous_valid = group["Valid"].shift(
        fill_value=False
    )

    previous_date = group["Date"].shift()

    # Only use truly adjacent market-observation intervals.
    usable_transition = (
        group["Valid"]
        & previous_valid
        & group["Forecast_As_Of"].eq(previous_date)
    )

    current = group["Exception"]
    previous = group["Exception"].shift()

    n00 = int(
        (usable_transition & previous.eq(0) & current.eq(0)).sum()
    )
    n01 = int(
        (usable_transition & previous.eq(0) & current.eq(1)).sum()
    )
    n10 = int(
        (usable_transition & previous.eq(1) & current.eq(0)).sum()
    )
    n11 = int(
        (usable_transition & previous.eq(1) & current.eq(1)).sum()
    )

    counts = {
        "n00": n00, "n01": n01,
        "n10": n10, "n11": n11,
        "Transitions": n00 + n01 + n10 + n11,
    }

    n0 = n00 + n01
    n1 = n10 + n11
    total = n0 + n1

    # The chi-square approximation is unreliable
    # with too few exception-related transitions.
    if (
        total == 0
        or n0 == 0
        or n1 == 0
        or (n01 + n11) < 5
    ):
        return {
            **counts,
            "LR_IND": np.nan,
            "p_IND": np.nan,
        }

    pi01 = n01 / n0
    pi11 = n11 / n1
    pi = (n01 + n11) / total

    def log_likelihood(success, trials, probability):
        return (
            xlogy(success, probability)
            + xlogy(trials - success, 1 - probability)
        )

    ll_null = log_likelihood(
        n01 + n11, total, pi
    )

    ll_alt = (
        log_likelihood(n01, n0, pi01)
        + log_likelihood(n11, n1, pi11)
    )

    lr = max(0.0, 2.0 * (ll_alt - ll_null))

    return {
        **counts,
        "LR_IND": float(lr),
        "p_IND": float(chi2.sf(lr, df=1)),
    }


def conditional_coverage_test(lr_uc, lr_ind):
    """Combined unconditional and independence test."""
    if not (
        np.isfinite(lr_uc)
        and np.isfinite(lr_ind)
    ):
        return {
            "LR_CC": np.nan,
            "p_CC": np.nan,
        }

    lr_cc = lr_uc + lr_ind

    return {
        "LR_CC": float(lr_cc),
        "p_CC": float(chi2.sf(lr_cc, df=2)),
    }

def es_diagnostics(valid, confidence):
    """Descriptive ES and tail-calibration diagnostics."""
    if valid.empty:
        return {
            "Tail_Count": 0,
            "Realized_Tail_Loss": np.nan,
            "Predicted_Tail_ES": np.nan,
            "ES_Ratio": np.nan,
            "ES_Moment_Mean": np.nan,
        }

    tail = valid[valid["Exception"] == 1]
    tail_count = len(tail)

    if tail_count:
        realized = float(tail["Loss"].mean())
        predicted = float(tail["ES"].mean())

        ratio = (
            realized / predicted
            if predicted > 0 else np.nan
        )
    else:
        realized = np.nan
        predicted = np.nan
        ratio = np.nan

    alpha = 1.0 - confidence

    # Calibration moment for continuous loss distributions:
    # E[(L - VaR)+] / alpha = E[ES - VaR]
    residual = (
        np.maximum(
            valid["Loss"].to_numpy()
            - valid["VaR"].to_numpy(),
            0.0,
        ) / alpha
        - (
            valid["ES"].to_numpy()
            - valid["VaR"].to_numpy()
        )
    )

    return {
        "Tail_Count": tail_count,
        "Realized_Tail_Loss": realized,
        "Predicted_Tail_ES": predicted,
        "ES_Ratio": ratio,
        "ES_Moment_Mean": float(np.mean(residual)),
    }


def var_pinball_score(valid, confidence):
    """Quantile loss: lower is better on a common sample."""
    if valid.empty:
        return np.nan

    loss = valid["Loss"].to_numpy()
    var = valid["VaR"].to_numpy()

    score = (
        (confidence - (loss < var).astype(float))
        * (loss - var)
    )

    return float(np.mean(score))

def summarize_models(df, sample_name):
    """Run all diagnostics for each model and confidence."""
    results = []

    for (model, confidence), group in df.groupby(
        ["Model", "Confidence_Level"]
    ):
        group = group.sort_values("Date").copy()
        valid = group[group["Valid"]].copy()

        n = len(valid)
        if n == 0:
            continue

        exceptions = valid["Exception"].astype(int)
        x = int(exceptions.sum())

        uc = kupiec_test(exceptions, confidence)
        ind = christoffersen_test(group)

        cc = conditional_coverage_test(
            uc["LR_UC"],
            ind["LR_IND"],
        )

        es = es_diagnostics(valid, confidence)

        results.append({
            "Sample": sample_name,
            "Model": model,
            "Confidence_Level": confidence,
            "Observations": n,
            "Invalid_Forecasts": int((~group["Valid"]).sum()),
            "Exceptions": x,
            "Exception_Rate": x / n,
            "Expected_Rate": 1 - confidence,
            "VaR_Pinball_Score": var_pinball_score(
                valid, confidence
            ),
            **uc,
            **ind,
            **cc,
            **es,
        })

    return pd.DataFrame(results)


def make_common_sample(df):
    """Retain dates valid for all three models."""
    df = df.copy()

    valid = df[df["Valid"]]

    counts = valid.groupby(
        ["Date", "Confidence_Level"]
    )["Model"].nunique()

    common_keys = counts[
        counts == len(MODELS)
    ].index

    selected = df.set_index(
        ["Date", "Confidence_Level"]
    ).index.isin(common_keys)

    return df.loc[selected].copy()


def compare_models(results):
    """Create a presentation-friendly comparison table."""
    columns = [
        "Model",
        "Confidence_Level",
        "Observations",
        "Exceptions",
        "Exception_Rate",
        "Expected_Rate",
        "p_UC",
        "p_IND",
        "p_CC",
        "ES_Ratio",
        "ES_Moment_Mean",
        "VaR_Pinball_Score",
    ]

    available = results[
        results["Sample"] == "COMMON"
    ].copy()

    return available[columns].sort_values(
        ["Confidence_Level", "VaR_Pinball_Score"]
    )


if __name__ == "__main__":
    raise SystemExit("Run scripts/run_backtesting.py to generate the official backtesting outputs.")
