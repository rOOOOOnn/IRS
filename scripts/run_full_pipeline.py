"""Run preprocessing, validation, curve research, daily curves, and IRS pricing."""

from __future__ import annotations

import subprocess
import sys

from irs_project.data.inspect import PROJECT_ROOT


def _run(script: str) -> None:
    path = PROJECT_ROOT / "scripts" / script
    subprocess.run([sys.executable, str(path)], cwd=PROJECT_ROOT, check=True)


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "irs_project.data.preprocess"], cwd=PROJECT_ROOT, check=True
    )
    subprocess.run(
        [sys.executable, "-m", "irs_project.data.validate"], cwd=PROJECT_ROOT, check=True
    )
    for script in (
        "run_curve_validation.py",
        "build_daily_curves.py",
        "run_irs_pricing.py",
    ):
        _run(script)
    _write_completion_report()


def _write_completion_report() -> None:
    selection_path = PROJECT_ROOT / "outputs" / "curve_validation" / "selected_method.json"
    if not selection_path.exists():
        raise RuntimeError("Curve selection output is missing")
    import json

    import pandas as pd

    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    comparison = pd.read_csv(
        PROJECT_ROOT / "outputs" / "curve_validation" / "curve_method_comparison.csv"
    )
    pricing = pd.read_csv(PROJECT_ROOT / "outputs" / "pricing" / "irs_mtm_by_method.csv")
    pnl = pd.read_csv(PROJECT_ROOT / "outputs" / "pricing" / "irs_mtm_pnl.csv")
    selected = selection["selected_method"]
    initial = pricing.loc[
        (pricing["Method"] == selected) & (pricing["Valuation_Status"] == "SUCCESS")
    ].iloc[0]
    failures = int((pricing["Valuation_Status"] == "FAILED").sum())
    selected_values = pricing.loc[
        pricing["Method"] == selected, ["Date", "IRS_Market_Value"]
    ].rename(columns={"IRS_Market_Value": "Selected_Value"})
    impact = pricing.merge(selected_values, on="Date", how="left", validate="many_to_one")
    impact["Absolute_Difference"] = (impact["IRS_Market_Value"] - impact["Selected_Value"]).abs()
    impact_summary = (
        impact.groupby("Method")["Absolute_Difference"]
        .agg(Mean_Absolute_Difference="mean", Max_Absolute_Difference="max")
        .reset_index()
    )
    numeric_comparison = comparison.select_dtypes(include="number").columns
    comparison[numeric_comparison] = comparison[numeric_comparison].round(6)
    numeric_impact = impact_summary.select_dtypes(include="number").columns
    impact_summary[numeric_impact] = impact_summary[numeric_impact].round(2)

    def markdown_table(frame: pd.DataFrame) -> str:
        display = frame.copy().fillna("")
        headers = [str(column) for column in display.columns]
        rows = [headers, ["---"] * len(headers)]
        rows.extend(
            [str(value).replace("|", "\\|") for value in record]
            for record in display.itertuples(index=False, name=None)
        )
        return "\n".join("| " + " | ".join(row) + " |" for row in rows)

    text = "\n".join(
        [
            "# Final Completion Report",
            "",
            f"- Selected global interpolation method: `{selected}`.",
            "- Selection used Validation interior-node LOTO RMSE; Test results were excluded "
            "from method selection.",
            f"- Initial selected-method IRS market value: USD {initial['IRS_Market_Value']:,.2f}.",
            f"- Successful selected-method P&L dates: {len(pnl)}.",
            f"- Four-method valuation failures: {failures}.",
            "- Regime-dependent switching remains diagnostic rather than primary to avoid "
            "artificial MTM jumps.",
            "- Contract dates and undisclosed cash-flow conventions remain explicit assumptions "
            "in `config/contract.yaml`.",
            "- `zero_curve_panel.csv`, `zero_rate_changes.csv`, and the scenario repricing "
            "interface are ready for Member A.",
            "- `irs_mtm_pnl.csv` is ready for Member B.",
            "",
            "## Method Comparison",
            "",
            markdown_table(comparison),
            "",
            "## IRS Pricing Impact by Method",
            "",
            markdown_table(impact_summary),
            "",
        ]
    )
    (PROJECT_ROOT / "outputs" / "FINAL_COMPLETION_REPORT.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
