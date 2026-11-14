"""Plot full rolling forecasts with explicit failed-date coverage, without changing risk data."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from irs_project.data.inspect import PROJECT_ROOT  # noqa: E402
from irs_project.risk.models import MODELS  # noqa: E402


def write_figures(root: Path) -> None:
    directory = root / "outputs/risk"
    forecasts = pd.read_csv(directory / "risk_model_outputs.csv", parse_dates=["Date"])
    alignment = pd.read_csv(directory / "risk_pnl_alignment.csv", parse_dates=["Date"])
    if forecasts.empty:
        raise ValueError("No rolling risk forecasts to plot")
    figure_dir = directory / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    levels = sorted(forecasts.Confidence_Level.unique())
    for model in MODELS:
        fig, axes = plt.subplots(len(levels), 1, figsize=(13, 7), sharex=True, squeeze=False)
        for ax, alpha in zip(axes.flat, levels, strict=True):
            data = forecasts.loc[
                (forecasts.Model == model) & (forecasts.Confidence_Level == alpha)
            ].merge(alignment[["Date", "Realized_Loss"]], on="Date", validate="one_to_one")
            failed = data.VaR.isna()
            ax.plot(
                data.Date,
                data.Realized_Loss / 1000,
                color="0.65",
                lw=0.6,
                label="Realized total-P&L loss (matched intervals)",
            )
            ax.plot(data.Date, data.VaR / 1000, color="#d97706", lw=1, label=f"{alpha:.0%} VaR")
            ax.plot(data.Date, data.ES / 1000, color="#7c3aed", lw=1, label=f"{alpha:.0%} ES")
            ax.scatter(
                data.loc[failed, "Date"],
                [0] * int(failed.sum()),
                color="#b91c1c",
                s=10,
                marker="x",
                label=f"Unavailable forecasts: {failed.sum()}",
            )
            ax.set_ylabel("USD thousands")
            ax.grid(alpha=0.2)
            ax.legend(fontsize=8, loc="upper right")
        fig.suptitle(f"{model}: rolling out-of-sample risk forecasts")
        axes[-1, 0].set_xlabel("Target / realization date")
        fig.tight_layout()
        fig.savefig(figure_dir / f"{model.lower()}_rolling_var_es.png", dpi=160)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(13, 5))
    for model in MODELS:
        data = forecasts.loc[(forecasts.Model == model) & (forecasts.Confidence_Level == 0.99)]
        ax.plot(data.Date, data.VaR / 1000, lw=0.9, label=f"{model}: 99% VaR")
    ax.set(
        title="99% VaR across shared-engine risk models",
        xlabel="Target / realization date",
        ylabel="USD thousands",
    )
    ax.grid(alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figure_dir / "model_comparison_99_var.png", dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    write_figures(args.root)
    print(args.root / "outputs/risk/figures")


if __name__ == "__main__":
    main()
