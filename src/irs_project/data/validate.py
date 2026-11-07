"""Validate Phase 1 standardized output schemas and invariants."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from .inspect import configured_path, load_config

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "ois_quotes_long.csv": [
        "Date",
        "Ticker",
        "Tenor",
        "Rate_Raw",
        "Rate_Decimal",
        "Source",
        "Field",
        "Security_Description",
        "Quality_Flag",
    ],
    "ois_par_rates_wide.csv": [
        "Date",
        "OIS_1M",
        "OIS_3M",
        "OIS_6M",
        "OIS_1Y",
        "OIS_2Y",
        "OIS_3Y",
        "OIS_4Y",
        "OIS_5Y",
        "OIS_7Y",
        "OIS_10Y",
    ],
    "sofr_fixings.csv": ["Date", "SOFR_Raw", "SOFR_Decimal", "Quality_Flag"],
    "sofr_index.csv": ["Date", "SOFR_Index", "Quality_Flag"],
    "data_coverage.csv": [
        "File_Name",
        "Ticker",
        "First_Valid_Observation",
        "Last_Valid_Observation",
    ],
    "data_manifest.csv": ["File_Name", "Relative_Path", "SHA256", "Processing_Status"],
}


def validate_outputs(config: dict[str, Any]) -> list[str]:
    output_directory = configured_path(config, "processed_directory")
    errors: list[str] = []
    frames: dict[str, pd.DataFrame] = {}
    for name, columns in REQUIRED_COLUMNS.items():
        path = output_directory / name
        if not path.exists():
            errors.append(f"Missing output: {name}")
            continue
        frame = pd.read_csv(path)
        frames[name] = frame
        missing_columns = [column for column in columns if column not in frame.columns]
        if missing_columns:
            errors.append(f"{name} missing columns: {missing_columns}")

    long = frames.get("ois_quotes_long.csv")
    if long is not None:
        if long.duplicated(["Date", "Ticker"]).any():
            errors.append("ois_quotes_long.csv contains duplicate Date/Ticker rows")
        numeric = pd.to_numeric(long["Rate_Decimal"], errors="coerce")
        raw = pd.to_numeric(long["Rate_Raw"], errors="coerce")
        comparable = numeric.notna() & raw.notna()
        if (
            comparable.any()
            and not ((numeric[comparable] - raw[comparable] / 100).abs() < 1e-12).all()
        ):
            errors.append("Rate_Decimal is not consistent with inferred percentage conversion")

    wide = frames.get("ois_par_rates_wide.csv")
    if wide is not None and not wide.empty:
        dates = pd.to_datetime(wide["Date"], errors="coerce")
        if (dates < pd.Timestamp(config["data"]["main_sample_start"])).any():
            errors.append("ois_par_rates_wide.csv includes pre-main-sample dates")
        if dates.duplicated().any():
            errors.append("ois_par_rates_wide.csv contains duplicate dates")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    arguments = parser.parse_args()
    errors = validate_outputs(load_config(arguments.config))
    if errors:
        raise SystemExit("Validation failed:\n- " + "\n- ".join(errors))
    print("All required Phase 1 outputs passed validation.")


if __name__ == "__main__":
    main()
