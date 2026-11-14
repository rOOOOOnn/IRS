"""Rolling zero-factor forecasts aligned to next-observation total IRS P&L."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from irs_project.curves.curve_factory import curve_from_market_row
from irs_project.data.load_market_data import load_yaml
from irs_project.pricing.contract import IRSContract
from irs_project.pricing.floating_leg import SofrHistory
from irs_project.pricing.risk_horizon import HorizonRepricer
from irs_project.utils.conventions import calendar_from_name
from irs_project.utils.dates import to_ql_date

from .models import MODELS, OUTPUT_COLUMNS, empirical_var_es, generate_shocks

LOGGER = logging.getLogger(__name__)


def read_dates(path):
    frame = pd.read_csv(path, parse_dates=["Date"])
    if frame["Date"].isna().any() or frame["Date"].duplicated().any():
        raise ValueError(f"Invalid/duplicate dates: {path}")
    if (frame["Date"] != frame["Date"].dt.normalize()).any():
        raise ValueError(f"Non-daily timestamps: {path}")
    return frame.sort_values("Date").set_index("Date")


def validate_config(config, factor_count):
    if config["window"] < 20 or config["simulations"] < 100 or config["batch_size"] < 1:
        raise ValueError("Invalid window/simulation/batch size")
    if not 0 < config["ewma_decay"] < 1:
        raise ValueError("Invalid EWMA decay")
    if not 1 <= config["pca_factors"] <= factor_count:
        raise ValueError("Invalid PCA factors")
    levels = config["confidence_levels"]
    if not levels or len(levels) != len(set(levels)) or not all(0 < a < 1 for a in levels):
        raise ValueError("Invalid confidence levels")
    if config["forecast_horizon"] != "1D":
        raise ValueError("Only the documented next-observation 1D horizon is supported")


def prepare_changes(changes, levels, dates, tenors, sample_start):
    """Check source changes, level reconciliation, gaps and publication-calendar anomalies."""
    calendar = calendar_from_name("US_GOVERNMENT_BOND")
    columns = [f"Delta_Zero_{t}" for t in tenors]
    zero_columns = [f"Zero_{t}" for t in tenors]
    missing = (set(columns) - set(changes)) | (set(zero_columns) - set(levels))
    if missing:
        raise ValueError(f"Missing risk factors: {sorted(missing)}")
    previous = levels.index.to_series().shift()
    accepted, audit = [], []
    for date, row in changes.iterrows():
        reason = ""
        start = previous.get(date, pd.NaT)
        shock = row[columns].to_numpy(dtype=float)
        if date < sample_start:
            reason = "BEFORE_TRAINING_START"
        elif pd.isna(start):
            reason = "NO_PREVIOUS_ZERO_CURVE"
        elif start not in dates or date not in dates:
            reason = "DATE_NOT_IN_MARKET_CALENDAR"
        elif dates.get_loc(date) - dates.get_loc(start) != 1:
            reason = "MULTI_OBSERVATION_CHANGE"
        elif not calendar.isBusinessDay(to_ql_date(date)) or not calendar.isBusinessDay(
            to_ql_date(start)
        ):
            reason = "NONBUSINESS_CURVE_DATE"
        elif not np.isfinite(shock).all():
            reason = "MISSING_OR_NONFINITE_CHANGE"
        else:
            actual = (levels.loc[date, zero_columns] - levels.loc[start, zero_columns]).to_numpy(
                dtype=float
            )
            if not np.isfinite(actual).all():
                reason = "MISSING_OR_NONFINITE_LEVEL"
            elif not np.allclose(actual, shock, rtol=1e-8, atol=1e-12):
                reason = "CHANGE_LEVEL_MISMATCH"
        accepted.append(not reason)
        audit.append(
            {
                "Date": date,
                "Previous_Date": start,
                "Status": "EXCLUDED" if reason else "VALID",
                "Reason": reason,
            }
        )
    return changes.loc[np.array(accepted), columns], pd.DataFrame(audit)


def run(root: Path, *, max_dates=None, overrides=None):
    root = Path(root)
    project = load_yaml(root / "config/project.yaml")
    curve_config = load_yaml(root / "config/curve.yaml")
    config = load_yaml(root / "config/risk.yaml")["risk"]
    config.update(overrides or {})
    tenors = list(curve_config["required_pricing_tenors"])
    validate_config(config, len(tenors))
    contract = IRSContract.from_config(load_yaml(root / "config/contract.yaml"))
    contract.validate()
    # The shared engine currently does not implement alternate SOFR observation conventions.
    if contract.observation_lookback_days or contract.observation_shift or contract.lockout_days:
        raise ValueError("Configured SOFR observation conventions are unsupported by shared engine")
    if contract.valuation_basis != "EX_CASHFLOW":
        raise ValueError("Risk P&L requires the existing EX_CASHFLOW pricing convention")
    selected_path = root / "outputs/curve_validation/selected_method.json"
    selection = json.loads(selected_path.read_text())
    if selection.get("selection_dataset") not in ("TRAINING", "VALIDATION"):
        raise ValueError("Curve selection must be frozen before test evaluation")
    method = selection["selected_method"]
    processed = root / "data/processed"
    market = read_dates(processed / "ois_par_rates_wide.csv")
    levels = read_dates(root / "outputs/curves/zero_curve_panel.csv")
    changes = read_dates(root / "outputs/curves/zero_rate_changes.csv")
    pnl = read_dates(root / "outputs/pricing/irs_mtm_pnl.csv")
    for name, frame in (("zero levels", levels),):
        if (
            "Interpolation_Method" not in frame
            or not frame["Interpolation_Method"].eq(method).all()
        ):
            raise ValueError(f"{name} are inconsistent with frozen curve selection")
    history = SofrHistory.from_frames(
        pd.read_csv(processed / "sofr_fixings.csv", parse_dates=["Date"]),
        pd.read_csv(processed / "sofr_index.csv", parse_dates=["Date"]),
    )
    for series in (history.index, history.fixings):
        if series.index.has_duplicates or series.index.isna().any():
            raise ValueError("Duplicate/invalid SOFR history dates")
    valid, audit = prepare_changes(
        changes,
        levels,
        market.index,
        tenors,
        pd.Timestamp(project["splits"]["training"]["start"]),
    )
    start = pd.Timestamp(project["splits"]["test"]["start"])
    end = pd.Timestamp(project["splits"]["test"]["end"] or levels.index.max())
    targets = market.index[(market.index >= start) & (market.index <= end)]
    if max_dates is not None:
        targets = targets[:max_dates]
    out = root / ("outputs/risk_smoke" if max_dates is not None else "outputs/risk")
    out.mkdir(parents=True, exist_ok=True)
    audit.to_csv(out / "risk_factor_audit.csv", index=False, date_format="%Y-%m-%d")
    rows, diagnostics, alignment = [], [], []
    calendar = calendar_from_name(curve_config["curve"]["calendar"])
    pnl_previous = pnl.index.to_series().shift()
    for number, target in enumerate(targets, 1):
        position = market.index.get_loc(target)
        cutoff = market.index[position - 1] if position else pd.NaT
        window = valid.loc[:cutoff].tail(config["window"]) if pd.notna(cutoff) else valid.iloc[:0]
        context = {
            "Date": target,
            "Information_Cutoff": cutoff,
            "Forecast_Horizon": config["forecast_horizon"],
            "Calendar_Days": (target - cutoff).days if pd.notna(cutoff) else None,
            "Window_Count": len(window),
            "Window_Start": window.index.min() if len(window) else pd.NaT,
            "Window_End": window.index.max() if len(window) else pd.NaT,
        }
        align = {**context, "Realized_Loss": np.nan, "Alignment_Status": "UNAVAILABLE"}
        if target in pnl.index:
            align["PnL_Previous_Date"] = pnl_previous.loc[target]
            if pnl_previous.loc[target] == cutoff:
                record = pnl.loc[target]
                if (
                    record["Valuation_Status"] in ("SUCCESS", "MATURED")
                    and np.isfinite(record[["Loss", "Total_PnL"]].to_numpy(dtype=float)).all()
                    and np.isclose(record["Loss"], -record["Total_PnL"], atol=1e-6, rtol=0)
                ):
                    align.update(Realized_Loss=float(record["Loss"]), Alignment_Status="MATCHED")
            else:
                align["Alignment_Status"] = "PNL_INTERVAL_MISMATCH"
        issues = []
        if cutoff not in levels.index:
            issues.append("MISSING_CUTOFF_CURVE")
        if target not in levels.index:
            issues.append("MISSING_TARGET_CURVE")
        if cutoff not in history.index.index:
            issues.append("MISSING_CUTOFF_SOFR_INDEX")
        if pd.notna(cutoff) and not calendar.isBusinessDay(to_ql_date(cutoff)):
            issues.append("NONBUSINESS_CUTOFF")
        if not calendar.isBusinessDay(to_ql_date(target)):
            issues.append("NONBUSINESS_TARGET")
        if align["Alignment_Status"] != "MATCHED":
            issues.append(align["Alignment_Status"])
        context["Data_Issues"] = ";".join(issues)
        context["PnL_Alignment_Status"] = align["Alignment_Status"]
        alignment.append({**align, "Data_Issues": context["Data_Issues"]})
        common_error, repricer = "", None
        try:
            if align["Alignment_Status"] == "PNL_INTERVAL_MISMATCH":
                raise ValueError("Realized PnL interval differs from forecast horizon")
            if pd.isna(cutoff) or cutoff not in levels.index:
                raise ValueError("Missing cutoff curve")
            if not calendar.isBusinessDay(to_ql_date(cutoff)) or not calendar.isBusinessDay(
                to_ql_date(target)
            ):
                raise ValueError("Nonbusiness forecast/cutoff date")
            if len(window) < config["window"]:
                raise ValueError("Insufficient valid rolling history")
            # Only cutoff information is passed to curve construction and repricing.
            curve = curve_from_market_row(
                market.loc[[cutoff]].reset_index(), cutoff, method, curve_config
            )
            repricer = HorizonRepricer(cutoff, target, curve, curve_config, contract, history)
            if cutoff not in pnl.index:
                raise ValueError("Missing main-engine cutoff valuation")
            if pnl.loc[cutoff, "Valuation_Status"] not in ("SUCCESS", "MATURED"):
                raise ValueError("Main-engine cutoff valuation has failed status")
            baseline_error = abs(repricer.base.market_value - pnl.loc[cutoff, "IRS_Market_Value"])
            if not np.isfinite(baseline_error) or baseline_error > 1e-5:
                raise ValueError(f"Main engine baseline mismatch: {baseline_error}")
            context.update(
                Zero_Shock_Error=repricer.zero_error,
                Horizon_Zero_Error=repricer.zero_horizon_error,
                Main_Pricing_Error=baseline_error,
                Base_Market_Value=repricer.base.market_value,
                Projected_Net_Cashflow=repricer.cashflow,
                Zero_Shock_Horizon_Value=repricer.zero_horizon,
            )
        except Exception as error:
            common_error = f"{type(error).__name__}: {error}"
        for model_id, model in enumerate(MODELS):
            error = common_error
            stats = {}
            forecasts = {}
            if not error:
                try:
                    # Date/model keyed streams are reproducible under slicing and restarts.
                    seed = np.random.SeedSequence([config["seed"], cutoff.toordinal(), model_id])
                    shocks, stats = generate_shocks(
                        model, window.to_numpy(dtype=float), config, np.random.default_rng(seed)
                    )
                    losses = np.concatenate(
                        [
                            repricer.losses(shocks[i : i + config["batch_size"]])
                            for i in range(0, len(shocks), config["batch_size"])
                        ]
                    )
                    if not np.isfinite(losses).all():
                        raise ValueError("Nonfinite losses; no scenarios were removed")
                    forecasts = {
                        a: empirical_var_es(losses, a) for a in config["confidence_levels"]
                    }
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
            for alpha in config["confidence_levels"]:
                var, es = forecasts.get(alpha, (np.nan, np.nan))
                rows.append(
                    {
                        "Date": target,
                        "Model": model,
                        "Confidence_Level": alpha,
                        "Forecast_Horizon": config["forecast_horizon"],
                        "VaR": var,
                        "ES": es,
                        "Forecast_As_Of": cutoff,
                    }
                )
            diagnostics.append(
                {
                    **context,
                    "Model": model,
                    **stats,
                    "Status": "FAILED" if error else "SUCCESS",
                    "Reason": error,
                }
            )
        if number % 25 == 0 or number == len(targets):
            LOGGER.info("Risk forecasts: %s/%s target dates", number, len(targets))
    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    diagnostic = pd.DataFrame(diagnostics)
    result.to_csv(out / "risk_model_outputs.csv", index=False, date_format="%Y-%m-%d")
    diagnostic.to_csv(out / "risk_forecast_diagnostics.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(alignment).to_csv(
        out / "risk_pnl_alignment.csv", index=False, date_format="%Y-%m-%d"
    )
    manifest_paths = [
        "config/contract.yaml",
        "config/curve.yaml",
        "config/project.yaml",
        "config/risk.yaml",
        "outputs/curves/zero_rate_changes.csv",
        "outputs/curves/zero_curve_panel.csv",
        "outputs/curve_validation/selected_method.json",
        "outputs/pricing/irs_mtm_pnl.csv",
        "data/processed/ois_par_rates_wide.csv",
        "data/processed/sofr_index.csv",
        "data/processed/sofr_fixings.csv",
        "src/irs_project/risk/models.py",
        "src/irs_project/risk/rolling.py",
        "src/irs_project/pricing/risk_horizon.py",
        "src/irs_project/pricing/valuation.py",
    ]
    manifest = {
        "parameters": config,
        "selected_curve_method": method,
        "risk_factors": tenors,
        "test_start": str(start.date()),
        "test_end": str(end.date()),
        "target_dates": len(targets),
        "output_rows": len(result),
        "successful_model_dates": int(diagnostic["Status"].eq("SUCCESS").sum()),
        "failed_model_dates": int(diagnostic["Status"].eq("FAILED").sum()),
        "partial_run": max_dates is not None,
        "forecast_date_meaning": "Date is realization/target date; Forecast_As_Of is cutoff EOD",
        "horizon": "1D = next observed market interval; actual calendar duration in diagnostics",
        "pnl": "V(target) - V(cutoff) + net settled cashflows over (cutoff,target]",
        "future_sofr": "Deterministic cutoff-curve projection; never realized future Index",
        "fixing_availability": "Index dated t is assumed known at end-of-day t, as main engine",
        "negative_quantiles": "Floor output VaR/ES at zero to honor positive-loss interface",
        "source_sha256": {
            p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in manifest_paths
        },
    }
    (out / "risk_run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return result, diagnostic
