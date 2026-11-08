"""Run four-method LOTO validation and select the global curve method."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from irs_project.curves.bootstrap import build_ois_curve  # noqa: E402
from irs_project.curves.comparison import (  # noqa: E402
    attach_regime,
    select_global_method,
    summarize_errors,
)
from irs_project.curves.curve_regimes import (  # noqa: E402
    add_curve_regimes,
    fit_regime_thresholds,
)
from irs_project.curves.loto_validation import (  # noqa: E402
    run_loto_validation,
    run_multi_tenor_holdouts,
)
from irs_project.data.inspect import PROJECT_ROOT  # noqa: E402
from irs_project.data.load_market_data import (  # noqa: E402
    load_curve_config,
    load_market_data,
    quotes_for_date,
)
from irs_project.data.merge import assign_split  # noqa: E402
from irs_project.data.validate_market_data import validate_curve_inputs  # noqa: E402
from irs_project.utils.conventions import (  # noqa: E402
    business_day_convention_from_name,
    calendar_from_name,
)
from irs_project.utils.dates import from_ql_date, tenor_to_period, to_ql_date  # noqa: E402
from irs_project.utils.logging import configure_logging  # noqa: E402


def _representative_figures(
    market: pd.DataFrame,
    config: dict,
    output_directory: Path,
) -> None:
    preferred = pd.Timestamp("2023-05-01")
    date = preferred if preferred in set(market["Date"]) else pd.Timestamp(market["Date"].iloc[-1])
    quotes = quotes_for_date(market, date, config["tenors"])
    calendar = calendar_from_name(config["curve"]["calendar"])
    convention = business_day_convention_from_name(config["curve"]["business_day_convention"])
    start = to_ql_date(date)
    query_dates = [
        from_ql_date(calendar.advance(start, tenor_to_period(f"{month}M"), convention))
        for month in range(1, 61)
    ]
    curves = {method: build_ois_curve(date, quotes, method, config) for method in config["methods"]}
    for value_name, getter, ylabel, filename in (
        ("Zero rate", "zero_rate", "Continuous zero rate", "zero_curve_comparison.png"),
        ("Discount factor", "discount_factor", "Discount factor", "discount_curve_comparison.png"),
    ):
        fig, ax = plt.subplots(figsize=(10, 6))
        for method, curve in curves.items():
            ax.plot(
                query_dates,
                [getattr(curve, getter)(query_date) for query_date in query_dates],
                label=method,
            )
        ax.set(title=f"{value_name} comparison on {date.date()}", xlabel="Maturity", ylabel=ylabel)
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(output_directory / filename, dpi=160)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 6))
    for method, curve in curves.items():
        forwards = []
        previous = date
        for query_date in query_dates:
            forwards.append(curve.forward_rate(previous, query_date))
            previous = query_date
        ax.plot(query_dates, forwards, label=method)
    ax.set(
        title=f"Monthly forward-rate comparison on {date.date()}",
        xlabel="Forward period end",
        ylabel="Continuous forward rate",
    )
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_directory / "forward_curve_comparison.png", dpi=160)
    plt.close(fig)


def _validation_figures(
    loto: pd.DataFrame,
    tenor: pd.DataFrame,
    regime: pd.DataFrame,
    output_directory: Path,
) -> None:
    interior = loto.loc[(loto["Status"] == "SUCCESS") & (loto["Evaluation_Type"] == "INTERIOR")]
    fig, ax = plt.subplots(figsize=(10, 6))
    for method, group in interior.groupby("Method"):
        clipped = group["Error_bps"].clip(-25, 25)
        ax.hist(clipped, bins=60, alpha=0.35, density=True, label=method)
    ax.set(
        title="LOTO interior-node error distribution (clipped to ±25 bps)",
        xlabel="Error (bps)",
        ylabel="Density",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_directory / "loto_error_distribution.png", dpi=160)
    plt.close(fig)

    validation = tenor.loc[
        (tenor["Dataset"] == "VALIDATION") & (tenor["Evaluation_Type"] == "INTERIOR")
    ]
    pivot = validation.pivot(index="Held_Out_Tenor", columns="Method", values="MAE_bps")
    ax = pivot.plot(kind="bar", figsize=(11, 6))
    ax.set(title="Validation LOTO MAE by tenor", xlabel="Held-out tenor", ylabel="MAE (bps)")
    ax.grid(axis="y", alpha=0.25)
    ax.figure.tight_layout()
    ax.figure.savefig(output_directory / "tenor_level_mae.png", dpi=160)
    plt.close(ax.figure)

    validation_regime = regime.loc[regime["Dataset"] == "VALIDATION"]
    if not validation_regime.empty:
        pivot = validation_regime.pivot(index="Curve_Regime", columns="Method", values="RMSE_bps")
        ax = pivot.plot(kind="bar", figsize=(11, 6))
        ax.set(
            title="Validation RMSE by curve regime",
            xlabel="Curve regime",
            ylabel="RMSE (bps)",
        )
        ax.grid(axis="y", alpha=0.25)
        ax.figure.tight_layout()
        ax.figure.savefig(output_directory / "curve_regime_performance.png", dpi=160)
        plt.close(ax.figure)


def _recommendation_text(
    comparison: pd.DataFrame,
    selected_method: str,
    ranking: pd.DataFrame,
    thresholds: dict,
    regime_mapping: dict[str, str],
) -> str:
    training = comparison.loc[comparison["Dataset"] == "TRAINING"].sort_values("RMSE_bps")
    training_best = str(training.iloc[0]["Method"]) if not training.empty else "Unavailable"
    validation_best = str(ranking.iloc[0]["Method"])
    supported = training_best == validation_best
    return "\n".join(
        [
            "# Final Curve Method Recommendation",
            "",
            f"- Training RMSE winner: `{training_best}`.",
            f"- Validation RMSE winner: `{validation_best}`.",
            f"- Validation supports the Training winner: `{supported}`.",
            f"- Selected global method: `{selected_method}`.",
            "- Test results were not used for selection.",
            "- The main comparison uses interior LOTO nodes; endpoints are reported separately.",
            "- Regime-dependent switching is not adopted as the primary method because method "
            "switches can create artificial MTM changes; the mapping below remains diagnostic.",
            "",
            "## Frozen Training Regime Thresholds",
            "",
            f"- Flat absolute slope threshold: {thresholds['flat_slope_absolute']:.8f}.",
            f"- Absolute curvature threshold: {thresholds['curvature_absolute']:.8f}.",
            "",
            "## Training Diagnostic Best Method by Regime",
            "",
            *[f"- {regime}: `{method}`" for regime, method in sorted(regime_mapping.items())],
            "",
            "## Limitations",
            "",
            "Contract and OIS cash-flow conventions not present in the disclosure remain "
            "explicit research assumptions. LOTO measures cross-sectional interpolation "
            "performance and does not prove that one method is universally superior.",
            "",
        ]
    )


def main() -> None:
    logger = configure_logging()
    config = load_curve_config()
    bundle = load_market_data()
    errors = validate_curve_inputs(bundle.curve_inputs_5y, config)
    if errors:
        raise SystemExit("Market validation failed:\n- " + "\n- ".join(errors))

    market = bundle.ois_quotes.copy()
    market["Dataset"] = assign_split(market["Date"], config["splits"])
    training = market.loc[market["Dataset"] == "TRAINING"]
    threshold_config = config["validation"]
    thresholds = fit_regime_thresholds(
        training,
        float(threshold_config["flat_slope_abs_quantile"]),
        float(threshold_config["curvature_abs_quantile"]),
    )
    market = add_curve_regimes(market, thresholds)

    output_directory = PROJECT_ROOT / "outputs" / "curve_validation"
    figure_directory = PROJECT_ROOT / "outputs" / "figures"
    output_directory.mkdir(parents=True, exist_ok=True)
    figure_directory.mkdir(parents=True, exist_ok=True)

    logger.info("Running LOTO validation for %s dates", len(market))
    loto = run_loto_validation(market, config)
    loto = attach_regime(loto, market)
    loto.to_csv(output_directory / "loto_detail.csv", index=False, date_format="%Y-%m-%d")

    main_loto = loto.loc[loto["Evaluation_Type"] == "INTERIOR"]
    comparison = summarize_errors(main_loto, ["Method", "Dataset"])
    tenor = summarize_errors(loto, ["Method", "Dataset", "Held_Out_Tenor", "Evaluation_Type"])
    regime = summarize_errors(main_loto, ["Method", "Dataset", "Curve_Regime"])
    minimum_regime_sample = int(config["validation"]["minimum_regime_sample"])
    regime["Sample_Status"] = regime["Sample_Count"].map(
        lambda count: "SUFFICIENT" if count >= minimum_regime_sample else "SAMPLE_INSUFFICIENT"
    )
    selected_method, ranking = select_global_method(comparison, config)

    robustness = run_multi_tenor_holdouts(market, config)
    robustness.to_csv(
        output_directory / "multiple_tenor_holdouts.csv", index=False, date_format="%Y-%m-%d"
    )
    comparison.to_csv(output_directory / "curve_method_comparison.csv", index=False)
    tenor.to_csv(output_directory / "tenor_level_comparison.csv", index=False)
    regime.to_csv(output_directory / "curve_regime_comparison.csv", index=False)

    training_regime = regime.loc[regime["Dataset"] == "TRAINING"].sort_values("RMSE_bps")
    regime_mapping = (
        training_regime.drop_duplicates("Curve_Regime")
        .set_index("Curve_Regime")["Method"]
        .to_dict()
    )
    threshold_payload = {
        "flat_slope_absolute": thresholds.flat_slope_absolute,
        "curvature_absolute": thresholds.curvature_absolute,
    }
    selection = {
        "selected_method": selected_method,
        "selection_dataset": config["validation"]["method_selection_dataset"],
        "selection_metric": config["validation"]["method_selection_metric"],
        "regime_thresholds": threshold_payload,
        "training_regime_mapping": regime_mapping,
    }
    (output_directory / "selected_method.json").write_text(
        json.dumps(selection, indent=2), encoding="utf-8"
    )
    recommendation = _recommendation_text(
        comparison, selected_method, ranking, threshold_payload, regime_mapping
    )
    (output_directory / "final_method_recommendation.md").write_text(
        recommendation, encoding="utf-8"
    )
    _representative_figures(market, config, figure_directory)
    _validation_figures(loto, tenor, regime, figure_directory)
    logger.info("Selected global method: %s", selected_method)


if __name__ == "__main__":
    main()
