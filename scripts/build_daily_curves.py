"""Build the selected-method daily curve database."""

from __future__ import annotations

import json

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from irs_project.curves.export import (  # noqa: E402
    build_daily_curve_database,
    write_curve_database,
)
from irs_project.data.inspect import PROJECT_ROOT  # noqa: E402
from irs_project.data.load_market_data import load_curve_config, load_market_data  # noqa: E402
from irs_project.utils.logging import configure_logging  # noqa: E402


def main() -> None:
    logger = configure_logging()
    config = load_curve_config()
    market = load_market_data().ois_quotes
    selection_path = PROJECT_ROOT / "outputs" / "curve_validation" / "selected_method.json"
    if not selection_path.exists():
        raise SystemExit("Run scripts/run_curve_validation.py before building daily curves")
    selected = json.loads(selection_path.read_text(encoding="utf-8"))["selected_method"]
    outputs = build_daily_curve_database(market, selected, config)
    output_directory = PROJECT_ROOT / "outputs" / "curves"
    write_curve_database(outputs, output_directory)

    calibration = outputs["curve_calibration.csv"]
    if not calibration.empty:
        daily = calibration.groupby("Date")["Error_bps"].apply(lambda values: values.abs().max())
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(pd.to_datetime(daily.index), daily.values)
        ax.set(
            title=f"Daily maximum calibration error — {selected}",
            xlabel="Date",
            ylabel="Maximum absolute error (bps)",
        )
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(PROJECT_ROOT / "outputs" / "figures" / "daily_calibration_error.png", dpi=160)
        plt.close(fig)
    logger.info("Daily curve database completed with %s", selected)


if __name__ == "__main__":
    main()
