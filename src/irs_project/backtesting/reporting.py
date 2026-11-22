
"""Reporting and validation for IRS backtesting."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


MODELS = ("HS", "EWMA", "PCA_MC")
LEVELS = (0.95, 0.99)


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

    required = {
        (model, level)
        for model in MODELS
        for level in LEVELS
    }

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
            combinations == required
            and len(group) == len(required)
        ):
            dates.append(date)

    return df[df["Date"].isin(dates)].copy()


def coverage(df, common):
    """Summarize candidate and common valid dates."""

    candidates = df["Date"].nunique()
    eligible = common["Date"].nunique()

    if not candidates or len(df) != candidates * 6:
        raise ValueError(
            "Expected exactly six forecasts per candidate date"
        )

    return {
        "Candidate_Dates": candidates,
        "Common_Valid_Dates": eligible,
        "Failed_Dates": candidates - eligible
    }


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
            f"**{coverage_data['Candidate_Dates']}**; "
            f"common valid dates: "
            f"**{coverage_data['Common_Valid_Dates']}**; "
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
            "Mean VaR | Mean ES | ES 95% CI | Pinball |",
            "|---|---:|---:|---:|---:|---:|---:|"
            "---:|---:|---|---:|"
        ])

        subset = results[
            results["Confidence_Level"] == confidence
        ]

        for row in subset.itertuples(index=False):

            ci = (
                f"[{fmt(row.ES_CI_Lower)}, "
                f"{fmt(row.ES_CI_Upper)}]"
            )

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
                f"| {ci} "
                f"| {fmt(row.VaR_Pinball_Score)} |"
            )

        lines.extend([
            "",
            f"Expected exceedance rate: {1-confidence:.0%}.",
            ""
        ])

    lines.extend([
        "## Excluded-Date Diagnostics",
        "",
        "| Failure Category | Forecast Rows |",
        "|---|---:|"
    ])

    for reason, count in failure_summary.items():
        lines.append(f"| {reason} | {count} |")

    lines.extend([
        "",
        "## Statistical Interpretation and Limitations",
        "",
        "- A p-value >= 0.05 means failure to reject, "
        "not proof that the model is correct.",
        "- Christoffersen uses consecutive valid intervals only.",
        "- Sparse exceedances can weaken chi-square approximations.",
        "- ES residual: max(Loss - VaR, 0) / (1-alpha) "
        "- (ES - VaR).",
        "- ES confidence intervals use an exploratory "
        "gap-aware block bootstrap.",
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
