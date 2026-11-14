"""Generate complete rolling OOS risk forecasts using the shared project pricing engine."""

from __future__ import annotations

import argparse
from pathlib import Path

from irs_project.data.inspect import PROJECT_ROOT
from irs_project.risk.rolling import run
from irs_project.utils.logging import configure_logging


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=PROJECT_ROOT)
    p.add_argument("--max-dates", type=int, help="Partial smoke run; NOT full OOS output")
    p.add_argument("--simulations", type=int, help="Override fixed configuration for smoke checks")
    args = p.parse_args()
    if args.max_dates is not None and args.max_dates < 1:
        p.error("--max-dates must be positive")
    if args.simulations is not None and args.max_dates is None:
        p.error("Use --simulations only with --max-dates; production uses config/risk.yaml")
    configure_logging()
    overrides = {"simulations": args.simulations} if args.simulations is not None else {}
    forecasts, diagnostics = run(args.root, max_dates=args.max_dates, overrides=overrides)
    print(f"Forecast rows: {len(forecasts)}")
    print(diagnostics["Status"].value_counts().to_string())
    directory = "risk_smoke" if args.max_dates is not None else "risk"
    print(args.root / "outputs" / directory / "risk_model_outputs.csv")


if __name__ == "__main__":
    main()
