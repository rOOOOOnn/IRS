
"""Final IRS out-of-sample backtesting runner.

Reads existing forecasts and pricing outputs.
Does not rerun risk models or IRS pricing.
"""

from pathlib import Path

import pandas as pd
import yaml

from irs_project.backtesting import backtest

from irs_project.backtesting.es_calibration import (
    bootstrap_es_ci
)

from irs_project.backtesting.reporting import (
    validate_and_scope,
    common_dates,
    coverage,
    render_report,
    plot_loss_vs_var
)


def decision(p_value):
    """5% significance-level decision."""

    if pd.isna(p_value):
        return "INSUFFICIENT"

    return (
        "REJECT"
        if p_value < 0.05
        else "NOT_REJECT"
    )


def main():

    root = Path(__file__).resolve().parents[1]

    # ---------------------------------------
    # 1. Read fixed project configuration
    # ---------------------------------------

    with (root / "config/project.yaml").open() as f:
        project_config = yaml.safe_load(f)

    with (root / "config/risk.yaml").open() as f:
        risk_config = yaml.safe_load(f)["risk"]

    assert sorted(
        risk_config["confidence_levels"]
    ) == [0.95, 0.99]

    assert risk_config["forecast_horizon"] == "1D"

    # ---------------------------------------
    # 2. Load existing model outputs
    # ---------------------------------------

    pnl, forecasts, alignment = (
        backtest.read_inputs()
    )

    diagnostics = pd.read_csv(
        root
        / "outputs/risk/risk_forecast_diagnostics.csv"
    )

    # ---------------------------------------
    # 3. Validate data alignment
    # ---------------------------------------

    aligned = backtest.prepare_data(
        pnl,
        forecasts,
        alignment
    )

    aligned = validate_and_scope(
        aligned,
        alignment,
        diagnostics,
        project_config
    )

    # All three models share one test sample.
    shared = common_dates(aligned)

    counts = coverage(aligned, shared)

    if counts["Common_Valid_Dates"] < 40:
        raise ValueError(
            "Insufficient common valid forecast dates"
        )

    # ---------------------------------------
    # 4. Run existing VaR backtesting
    # ---------------------------------------

    results = backtest.summarize_models(
        shared,
        "COMMON"
    )

    # ---------------------------------------
    # 5. Add ES calibration and average risk
    # ---------------------------------------

    additions = []

    for (model, confidence), group in shared.groupby(
        ["Model", "Confidence_Level"]
    ):

        valid = group[group["Valid"]]

        es_result = bootstrap_es_ci(
            group,
            confidence,
            block_length=10,
            simulations=2000
        )

        additions.append({
            "Model": model,
            "Confidence_Level": confidence,
            "Mean_VaR": valid["VaR"].mean(),
            "Mean_ES": valid["ES"].mean(),
            **es_result
        })

    additions = pd.DataFrame(additions)

    results = results.drop(
        columns=["ES_Moment_Mean"],
        errors="ignore"
    )

    results = results.merge(
        additions,
        on=["Model", "Confidence_Level"],
        validate="one_to_one"
    )

    # ---------------------------------------
    # 6. Statistical decisions
    # ---------------------------------------

    results["UC_Decision_5pct"] = (
        results["p_UC"].map(decision)
    )

    results["IND_Decision_5pct"] = (
        results["p_IND"].map(decision)
    )

    results["CC_Decision_5pct"] = (
        results["p_CC"].map(decision)
    )

    def es_decision(row):

        if pd.isna(row["ES_CI_Lower"]):
            return "UNAVAILABLE"

        if (
            row["ES_CI_Lower"] > 0
            or row["ES_CI_Upper"] < 0
        ):
            return "ZERO_OUTSIDE_CI"

        return "ZERO_IN_CI"

    results["ES_Diagnostic_Decision_5pct"] = (
        results.apply(es_decision, axis=1)
    )

    # ---------------------------------------
    # 7. Save outputs
    # ---------------------------------------

    output = root / "outputs/backtesting"
    output.mkdir(parents=True, exist_ok=True)

    aligned.to_csv(
        output / "backtest_detail.csv",
        index=False
    )

    shared[shared["Valid"]].to_csv(
        output / "common_sample_detail.csv",
        index=False
    )

    results.to_csv(
        output / "backtest_results.csv",
        index=False
    )

    # Report excluded forecasts without filling.
    excluded_dates = sorted(
        set(aligned["Date"]) - set(shared["Date"])
    )

    failed = aligned[
        aligned["Date"].isin(excluded_dates)
    ].copy()

    failed.to_csv(
        output / "excluded_forecasts.csv",
        index=False
    )

    failure_summary = (
        failed["Invalid_Reason"]
        .replace("", "OTHER_MODEL_FAILED")
        .value_counts()
    )

    # ---------------------------------------
    # 8. Generate report and figures
    # ---------------------------------------

    render_report(
        results,
        counts,
        failure_summary,
        output / "model_comparison.md"
    )

    plot_loss_vs_var(
        shared,
        output / "figures"
    )

    # ---------------------------------------
    # 9. Print summary
    # ---------------------------------------

    print("\nData coverage:")
    print(counts)

    print("\nFinal backtesting results:")

    display_columns = [
        "Model",
        "Confidence_Level",
        "Observations",
        "Exceptions",
        "p_UC",
        "p_IND",
        "p_CC",
        "ES_CI_Lower",
        "ES_CI_Upper"
    ]

    print(
        results[display_columns].to_string(
            index=False
        )
    )

    print("\nBacktesting completed.")
    print("Results saved in:", output)


if __name__ == "__main__":
    main()
