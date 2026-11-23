
"""Reporting and validation for IRS backtesting."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MODELS = ("HS", "EWMA", "PCA_MC")
LEVELS = (0.95, 0.99)
FORECAST_KEYS = {(model, level) for model in MODELS for level in LEVELS}

NON_BUSINESS = "NON_BUSINESS_FORECAST_OR_CUTOFF_DATE"
INTERVAL = "REALIZED_PNL_INTERVAL_MISMATCH"
MISSING_SOFR = "MISSING_EXACT_CUTOFF_SOFR_INDEX"
OTHER = "OTHER_UNCLASSIFIED"
FAILURE_CATEGORIES = (NON_BUSINESS, INTERVAL, MISSING_SOFR, OTHER)


def validate_and_scope(df, alignment, diagnostics, config):
    """Validate timestamps and diagnostic status."""

    test_cfg = config["splits"]["test"]

    start = pd.Timestamp(test_cfg["start"])
    end = (
        pd.Timestamp(test_cfg["end"])
        if test_cfg.get("end") else None
    )

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])

    if end is not None:
        df = df[df["Date"].between(start, end)].copy()
    else:
        df = df[df["Date"] >= start].copy()

    # Information cutoff from alignment output.
    align = alignment[
        ["Date", "Information_Cutoff"]
    ].copy()

    align["Date"] = pd.to_datetime(align["Date"])

    align["Information_Cutoff"] = pd.to_datetime(
        align["Information_Cutoff"]
    )

    # Forecast diagnostics.
    diag = diagnostics[
        ["Date", "Model", "Status", "Reason"]
    ].copy()

    diag["Date"] = pd.to_datetime(diag["Date"])

    if align["Date"].duplicated().any():
        raise ValueError("Duplicate alignment dates")

    if diag.duplicated(["Date", "Model"]).any():
        raise ValueError("Duplicate diagnostic keys")

    df = df.merge(
        align,
        on="Date",
        how="left",
        validate="many_to_one"
    )

    df = df.merge(
        diag,
        on=["Date", "Model"],
        how="left",
        validate="many_to_one"
    )

    for col in [
        "Forecast_As_Of",
        "PnL_Previous_Date",
        "Information_Cutoff"
    ]:
        df[col] = pd.to_datetime(df[col])

    # All required timestamps must refer to the same
    # information set and precede the realized-loss date.
    time_ok = (
        df["Forecast_As_Of"].notna()
        & df["Forecast_As_Of"].eq(
            df["Information_Cutoff"]
        )
        & df["Forecast_As_Of"].eq(
            df["PnL_Previous_Date"]
        )
        & df["Forecast_As_Of"].lt(df["Date"])
    )

    df["Valid"] = (
        df["Valid"].astype(bool)
        & time_ok
        & df["Status"].eq("SUCCESS")
    )

    df["Exception"] = np.where(
        df["Valid"],
        (df["Loss"] > df["VaR"]).astype(float),
        np.nan
    )

    df["Invalid_Reason"] = np.where(
        df["Valid"],
        "",
        np.where(
            ~time_ok,
            "TIME_ALIGNMENT",
            df["Reason"].fillna("INVALID_INPUT")
        )
    )

    return df


def common_dates(df):
    """Require all three models at both confidence levels."""

    valid = df[df["Valid"]]

    dates = []

    for date, group in valid.groupby("Date"):

        combinations = set(
            zip(
                group["Model"],
                group["Confidence_Level"]
            )
        )

        if (
            combinations == FORECAST_KEYS
            and len(group) == len(FORECAST_KEYS)
        ):
            dates.append(date)

    return df[df["Date"].isin(dates)].copy()


def coverage(df, common):
    """Summarize candidate and common valid dates."""

    candidates = df["Date"].nunique()
    eligible = common["Date"].nunique()

    if not candidates or any(
        len(group) != len(FORECAST_KEYS)
        or set(zip(group["Model"], group["Confidence_Level"])) != FORECAST_KEYS
        for _, group in df.groupby("Date")
    ):
        raise ValueError(
            "Expected exactly six forecasts per candidate date, one per model and confidence level"
        )

    return {
        "Candidate_Dates": candidates,
        "Common_Valid_Dates": eligible,
        "Failed_Dates": candidates - eligible
    }


def _failure_evidence(row):
    """Classify an invalid forecast using its model diagnostic and alignment."""
    if row.Status != "FAILED" or pd.isna(row.Reason):
        return OTHER, "No failed model diagnostic with a reason"

    reason = row.Reason
    if (
        pd.isna(row.Diagnostic_Cutoff)
        or row.Diagnostic_Cutoff != row.Information_Cutoff
        or row.Diagnostic_Alignment_Status != row.Alignment_Status
    ):
        return OTHER, "Model diagnostic and P&L alignment disagree"

    issues = set(str(row.Alignment_Data_Issues).split(";"))
    if "Realized PnL interval differs from forecast horizon" in reason:
        category = INTERVAL
        confirmed = (
            row.Alignment_Status == "PNL_INTERVAL_MISMATCH"
            and "PNL_INTERVAL_MISMATCH" in issues
            and pd.notna(row.PnL_Previous_Date)
            and row.PnL_Previous_Date != row.Information_Cutoff
        )
    elif "Nonbusiness forecast/cutoff date" in reason:
        category = NON_BUSINESS
        confirmed = bool(issues & {"NONBUSINESS_TARGET", "NONBUSINESS_CUTOFF"})
    elif "Missing exact cutoff SOFR Index" in reason:
        category = MISSING_SOFR
        confirmed = "MISSING_CUTOFF_SOFR_INDEX" in issues
    else:
        return OTHER, "Unrecognized model diagnostic reason"

    if confirmed:
        return category, "Confirmed by P&L alignment"
    return OTHER, f"P&L alignment did not corroborate {category}"


def classify_exclusions(aligned, shared, alignment, diagnostics):
    """Attach audit evidence and one mutually exclusive category per date."""
    excluded = aligned.loc[~aligned["Date"].isin(shared["Date"])]
    alignment_audit = alignment[["Date", "Data_Issues"]].rename(
        columns={"Data_Issues": "Alignment_Data_Issues"}
    )
    diagnostic_audit = diagnostics[
        ["Date", "Model", "Information_Cutoff", "PnL_Alignment_Status"]
    ].rename(columns={
        "Information_Cutoff": "Diagnostic_Cutoff",
        "PnL_Alignment_Status": "Diagnostic_Alignment_Status",
    })
    alignment_audit["Date"] = pd.to_datetime(alignment_audit["Date"])
    diagnostic_audit["Date"] = pd.to_datetime(diagnostic_audit["Date"])
    diagnostic_audit["Diagnostic_Cutoff"] = pd.to_datetime(
        diagnostic_audit["Diagnostic_Cutoff"]
    )
    excluded = excluded.merge(
        alignment_audit, on="Date", how="left", validate="many_to_one"
    ).merge(
        diagnostic_audit, on=["Date", "Model"], how="left", validate="many_to_one"
    )

    excluded["Failure_Category"] = OTHER
    excluded["Failure_Category_Detail"] = "Another forecast on this date was invalid"
    for row in excluded.loc[~excluded["Valid"]].itertuples():
        category, detail = _failure_evidence(row)
        excluded.loc[row.Index, ["Failure_Category", "Failure_Category_Detail"]] = (
            category, detail
        )

    for _, group in excluded.groupby("Date"):
        causes = group.loc[~group["Valid"], "Failure_Category"].unique()
        if len(causes) == 1:
            excluded.loc[group.index, "Failure_Category"] = causes[0]
            if causes[0] == OTHER:
                excluded.loc[group.index[group["Valid"]], "Failure_Category_Detail"] = (
                    "Another forecast on this date had an unclassified failure"
                )
        else:
            excluded.loc[group.index, "Failure_Category"] = OTHER
            excluded.loc[group.index, "Failure_Category_Detail"] = (
                "No single failure category for this date: "
                + ", ".join(sorted(causes))
                + ". "
                + group["Failure_Category_Detail"]
            )

    summary = excluded.groupby("Failure_Category").agg(
        Unique_Excluded_Dates=("Date", "nunique"),
        Excluded_Forecast_Rows=("Date", "size"),
    ).reindex(FAILURE_CATEGORIES, fill_value=0)
    summary.loc["TOTAL"] = summary.sum()
    return excluded, summary.reset_index()


def render_report(
    results,
    coverage_data,
    failure_summary,
    path
):
    """Write final Markdown comparison report."""

    lines = [
        "# IRS Out-of-Sample Backtesting & Model Comparison",
        "",
        "All results use the fixed common test sample.",
        "",
        (
            f"Candidate dates: "
            f"**{coverage_data['Candidate_Dates']}**, "
            f"common valid dates: "
            f"**{coverage_data['Common_Valid_Dates']}**, "
            f"excluded dates: "
            f"**{coverage_data['Failed_Dates']}**."
        ),
        "",
        "## VaR Coverage and ES Calibration",
        ""
    ]

    def fmt(value):
        return (
            "N/A"
            if pd.isna(value)
            else f"{value:,.4f}"
        )

    for confidence in LEVELS:

        lines.extend([
            f"### {confidence:.0%} Confidence Level",
            "",
            "| Model | N | Exceptions | Rate | "
            "Kupiec p | IND p | CC p | "
            "Mean VaR | Mean ES | Pinball |",
            "|---|---:|---:|---:|---:|---:|---:|"
            "---:|---:|---:|"
        ])

        subset = results[
            results["Confidence_Level"] == confidence
        ]

        for row in subset.itertuples(index=False):

            lines.append(
                f"| {row.Model} "
                f"| {row.Observations} "
                f"| {row.Exceptions} "
                f"| {row.Exception_Rate:.2%} "
                f"| {fmt(row.p_UC)} "
                f"| {fmt(row.p_IND)} "
                f"| {fmt(row.p_CC)} "
                f"| {fmt(row.Mean_VaR)} "
                f"| {fmt(row.Mean_ES)} "
                f"| {fmt(row.VaR_Pinball_Score)} |"
            )

        lines.extend([
            "",
            f"Expected exceedance rate: {1-confidence:.0%}.",
            ""
        ])

    lines.extend([
        "## ES Calibration Moment 95% CI",
        "",
        "The primary interval is asymmetric and pivotal. Its equal-tailed p-value tests "
        "whether the mean moment is zero. The symmetric interval and absolute-tail p-value "
        "use the same centered draws and show sensitivity to the inference method.",
        "",
        "| Model | Level | Moment mean | Pivotal CI | Equal-tailed p | Zero in pivotal CI | "
        "Symmetric CI | Absolute-tail p | Zero in symmetric CI |",
        "|---|---:|---:|---|---:|:---:|---|---:|:---:|",
    ])
    for row in results.itertuples(index=False):
        lower, upper = row.ES_Moment_CI_Lower, row.ES_Moment_CI_Upper
        sym_lower, sym_upper = row.ES_Moment_Symmetric_CI_Lower, row.ES_Moment_Symmetric_CI_Upper
        pivotal_zero = "N/A" if pd.isna(lower) else ("Yes" if lower <= 0 <= upper else "No")
        symmetric_zero = (
            "N/A" if pd.isna(sym_lower) else ("Yes" if sym_lower <= 0 <= sym_upper else "No")
        )
        lines.append(
            f"| {row.Model} | {row.Confidence_Level:.0%} | {fmt(row.ES_Moment_Mean)} "
            f"| [{fmt(lower)}, {fmt(upper)}] | {row.ES_Bootstrap_p:.6g} | {pivotal_zero} "
            f"| [{fmt(sym_lower)}, {fmt(sym_upper)}] "
            f"| {row.ES_Bootstrap_Symmetric_p:.6g} | {symmetric_zero} |"
        )
    lines.append("")

    lines.extend([
        "## Excluded-Date Diagnostics",
        "",
        "A date is excluded from the common sample if any forecast fails. "
        "Each excluded date and all of its forecast rows share one category. "
        "Model diagnostic reasons are checked against P&L alignment flags.",
        (
            f"Failed model diagnostics linked to exclusions: "
            f"**{coverage_data['Failed_Model_Diagnostics']}** "
            "(unique date/model pairs)."
        ),
        "",
        "| Failure Category | Unique Excluded Dates | Excluded Forecast Rows |",
        "|---|---:|---:|"
    ])

    for row in failure_summary.itertuples(index=False):
        lines.append(
            f"| {row.Failure_Category} | {row.Unique_Excluded_Dates} "
            f"| {row.Excluded_Forecast_Rows} |"
        )

    lines.extend([
        "",
        "## Statistical Interpretation and Limitations",
        "",
        "- A p-value >= 0.05 means failure to reject, "
        "not proof that the model is correct.",
        "- Christoffersen uses consecutive valid intervals only.",
        "- Sparse exceedances can weaken chi-square approximations.",
        "- The ES calibration moment is `max(Loss - VaR, 0) / (1 - alpha) "
        "- (ES - VaR)`. Its expected value is zero under correct joint "
        "VaR and ES calibration.",
        "- Mean ES averages the ES forecasts in USD. The 95% bootstrap "
        "interval estimates the mean of the ES calibration moment. "
        "These describe different quantities.",
        "- The gap-aware circular block bootstrap provides an exploratory "
        "unconditional ES calibration diagnostic. It cannot establish "
        "conditional ES calibration.",
        "- Bootstrap inference assumes sufficiently "
        "stationary and weakly dependent residuals.",
        "- Bootstrap results may depend on block length.",
        "- The ES Ratio is descriptive, "
        "not a standalone formal statistical test.",
        "- Pinball Score measures VaR quantile accuracy.",
        "- All model comparisons use the same dates.",
        "- No model parameters were recalibrated.",
        "",
        "## Figures",
        "",
        "Rolling Loss vs VaR figures are saved under "
        "`outputs/backtesting/figures/`.",
        ""
    ])

    Path(path).write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


def plot_loss_vs_var(df, output_dir):
    """Plot rolling actual loss and predicted VaR."""

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for confidence in LEVELS:
        for model in MODELS:

            subset = df[
                (df["Confidence_Level"] == confidence)
                & (df["Model"] == model)
                & (df["Valid"])
            ].sort_values("Date")

            if subset.empty:
                continue

            fig, ax = plt.subplots(figsize=(11, 4))

            ax.plot(
                subset["Date"],
                subset["Loss"],
                linewidth=0.8,
                label="Realized Loss"
            )

            ax.plot(
                subset["Date"],
                subset["VaR"],
                linewidth=1.0,
                label="Predicted VaR"
            )

            exceptions = subset[
                subset["Loss"] > subset["VaR"]
            ]

            ax.scatter(
                exceptions["Date"],
                exceptions["Loss"],
                marker="x",
                s=30,
                label="VaR Exceedance"
            )

            ax.set_title(
                f"{model} - {confidence:.0%} "
                "Rolling VaR Backtesting"
            )
            ax.set_xlabel("Date")
            ax.set_ylabel("USD")
            ax.legend()
            ax.grid(alpha=0.2)

            fig.autofmt_xdate()
            fig.tight_layout()

            name = (
                f"{model}_{int(confidence * 100)}_var.png"
            )

            fig.savefig(
                output_dir / name,
                dpi=150
            )

            plt.close(fig)
