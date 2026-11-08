"""Run four-method daily IRS valuation and selected-method P&L."""

from __future__ import annotations

import json

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from irs_project.data.inspect import PROJECT_ROOT  # noqa: E402
from irs_project.data.load_market_data import (  # noqa: E402
    load_contract_config,
    load_curve_config,
    load_market_data,
)
from irs_project.pricing.contract import IRSContract  # noqa: E402
from irs_project.pricing.daily_mtm import (  # noqa: E402
    build_daily_valuations,
    selected_method_pnl,
)
from irs_project.pricing.floating_leg import SofrHistory  # noqa: E402
from irs_project.utils.logging import configure_logging  # noqa: E402


def main() -> None:
    logger = configure_logging()
    curve_config = load_curve_config()
    contract = IRSContract.from_config(load_contract_config())
    bundle = load_market_data()
    history = SofrHistory.from_frames(bundle.sofr_fixings, bundle.sofr_index)
    selection_path = PROJECT_ROOT / "outputs" / "curve_validation" / "selected_method.json"
    if not selection_path.exists():
        raise SystemExit("Run scripts/run_curve_validation.py before IRS pricing")
    selected = json.loads(selection_path.read_text(encoding="utf-8"))["selected_method"]

    valuations = build_daily_valuations(
        bundle.ois_quotes,
        curve_config["methods"],
        curve_config,
        contract,
        history,
    )
    pricing_directory = PROJECT_ROOT / "outputs" / "pricing"
    validation_directory = PROJECT_ROOT / "outputs" / "curve_validation"
    pricing_directory.mkdir(parents=True, exist_ok=True)
    valuations.to_csv(
        pricing_directory / "irs_mtm_by_method.csv", index=False, date_format="%Y-%m-%d"
    )
    pnl = selected_method_pnl(valuations, selected, contract, history)
    pnl.to_csv(pricing_directory / "irs_mtm_pnl.csv", index=False, date_format="%Y-%m-%d")

    successful = valuations.loc[valuations["Valuation_Status"] == "SUCCESS"].copy()
    selected_values = successful.loc[successful["Method"] == selected, ["Date", "IRS_Market_Value"]]
    selected_values = selected_values.rename(columns={"IRS_Market_Value": "Selected_Value"})
    comparison = successful.merge(selected_values, on="Date", how="left", validate="many_to_one")
    comparison["Difference_vs_Selected_Method"] = (
        comparison["IRS_Market_Value"] - comparison["Selected_Value"]
    )
    denominator = comparison["Selected_Value"].abs().replace(0.0, pd.NA)
    comparison["Relative_Difference"] = comparison["Difference_vs_Selected_Method"] / denominator
    comparison[
        [
            "Date",
            "Method",
            "IRS_Market_Value",
            "Difference_vs_Selected_Method",
            "Relative_Difference",
        ]
    ].to_csv(
        validation_directory / "irs_pricing_method_comparison.csv",
        index=False,
        date_format="%Y-%m-%d",
    )

    pivot = successful.pivot(index="Date", columns="Method", values="IRS_Market_Value")
    fig, ax = plt.subplots(figsize=(11, 6))
    for method in pivot:
        ax.plot(pivot.index, pivot[method], label=method, linewidth=1)
    ax.set(title="Daily IRS market value by interpolation method", xlabel="Date", ylabel="USD")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PROJECT_ROOT / "outputs" / "figures" / "irs_mtm_by_method.png", dpi=160)
    plt.close(fig)
    logger.info("IRS pricing completed; selected method: %s", selected)


if __name__ == "__main__":
    main()
