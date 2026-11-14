"""Pricing, information-cutoff and rolling-forecast integration regressions."""

from __future__ import annotations

import json
from shutil import copy2

import numpy as np
import pandas as pd
import pytest

from irs_project.curves.curve_factory import curve_from_market_row
from irs_project.data.inspect import PROJECT_ROOT
from irs_project.data.load_market_data import load_yaml
from irs_project.pricing.contract import IRSContract
from irs_project.pricing.daily_mtm import _realized_net_cashflow
from irs_project.pricing.floating_leg import SofrHistory
from irs_project.pricing.risk_horizon import HorizonRepricer
from irs_project.pricing.scenario_repricing import build_scenario_curve, scenario_irs_value
from irs_project.pricing.schedule import build_payment_schedule
from irs_project.pricing.valuation import price_irs
from irs_project.risk.models import MODELS, OUTPUT_COLUMNS, empirical_var_es, generate_shocks
from irs_project.risk.rolling import prepare_changes, read_dates, run


@pytest.fixture
def inputs():
    root = PROJECT_ROOT
    cfg = load_yaml(root / "config/curve.yaml")
    contract = IRSContract.from_config(load_yaml(root / "config/contract.yaml"))
    market = pd.read_csv(root / "data/processed/ois_par_rates_wide.csv", parse_dates=["Date"])
    history = SofrHistory.from_frames(
        pd.read_csv(root / "data/processed/sofr_fixings.csv", parse_dates=["Date"]),
        pd.read_csv(root / "data/processed/sofr_index.csv", parse_dates=["Date"]),
    )
    method = json.loads((root / "outputs/curve_validation/selected_method.json").read_text())[
        "selected_method"
    ]
    return cfg, contract, market, history, method


@pytest.mark.parametrize(
    "cutoff,target",
    [
        ("2023-05-30", "2023-05-31"),
        ("2024-05-02", "2024-05-03"),
        ("2024-05-03", "2024-05-06"),
        ("2026-05-04", "2026-05-05"),
    ],
)
def test_batch_scalar_and_cashflows(inputs, cutoff, target):
    cfg, contract, market, history, method = inputs
    cutoff, target = pd.Timestamp(cutoff), pd.Timestamp(target)
    curve = curve_from_market_row(market, cutoff, method, cfg)
    pricer = HorizonRepricer(cutoff, target, curve, cfg, contract, history)
    n = len(pricer.tenors)
    shocks = np.array([np.zeros(n), np.linspace(-0.001, 0.001, n), np.full(n, 0.0005)])
    values = pricer.values(shocks)
    for shock, value in zip(shocks, values, strict=True):
        scenario = build_scenario_curve(
            target, pricer.rolled, dict(zip(pricer.tenors, shock, strict=True)), cfg
        )
        scalar = price_irs(target, scenario, contract, pricer.history)
        assert value == pytest.approx(scalar.market_value, abs=1e-6)
    direct, change = scenario_irs_value(
        cutoff,
        curve,
        dict.fromkeys(pricer.tenors, 0.0),
        cfg,
        contract,
        SofrHistory(history.fixings.loc[:cutoff], history.index.loc[:cutoff]),
    )
    assert direct.market_value == pytest.approx(pricer.base.market_value, abs=1e-6)
    assert change == pytest.approx(0, abs=1e-6)
    np.testing.assert_allclose(
        pricer.losses(shocks),
        pricer.base.market_value - values - pricer.cashflow,
        atol=1e-6,
    )
    if target == pd.Timestamp("2024-05-03"):
        assert pricer.cashflow > 100_000
        assert abs(pricer.losses(np.zeros((1, n)))[0]) < 10_000


def test_no_future_sofr(inputs):
    cfg, contract, market, history, method = inputs
    cutoff, target = pd.Timestamp("2024-04-30"), pd.Timestamp("2024-05-01")
    curve = curve_from_market_row(market, cutoff, method, cfg)
    before = HorizonRepricer(cutoff, target, curve, cfg, contract, history)
    corrupted = SofrHistory(history.fixings.copy(), history.index.copy())
    corrupted.index.loc[corrupted.index.index > cutoff] *= 50
    corrupted.fixings.loc[corrupted.fixings.index > cutoff] = 100
    after = HorizonRepricer(cutoff, target, curve, cfg, contract, corrupted)
    shocks = np.zeros((2, len(before.tenors)))
    np.testing.assert_array_equal(before.losses(shocks), after.losses(shocks))
    assert before.history.index.loc[target] != history.index.loc[target]


def test_models_and_fractional_es():
    rng = np.random.default_rng(42)
    x = rng.normal(size=(500, 8)) * 1e-4
    cfg = {"pca_factors": 8, "simulations": 100_000, "ewma_decay": 0.94}
    pca, info = generate_shocks("PCA_MC", x, cfg, rng)
    assert info["Explained_Variance"] == pytest.approx(1)
    np.testing.assert_allclose(np.cov(pca, rowvar=False), np.cov(x, rowvar=False), atol=2e-10)
    for model in MODELS:
        a, _ = generate_shocks(model, x, cfg, np.random.default_rng(5))
        b, _ = generate_shocks(model, x, cfg, np.random.default_rng(5))
        np.testing.assert_array_equal(a, b)
    assert empirical_var_es([0, 1, 2, 3], 0.625) == pytest.approx((2, 8 / 3))
    assert empirical_var_es([-3, -2, -1], 0.95) == (0, 0)


def test_changes_exclude_gaps_and_mismatches():
    dates = pd.bdate_range("2023-06-05", periods=5)
    levels = pd.DataFrame({"Zero_1Y": [0.01, 0.02, 0.03, 0.04]}, index=dates[[0, 1, 3, 4]])
    changes = levels.diff().rename(columns={"Zero_1Y": "Delta_Zero_1Y"})
    changes.loc[dates[4], "Delta_Zero_1Y"] = 0.02
    valid, audit = prepare_changes(changes, levels, dates, ["1Y"], dates[0])
    assert valid.index.tolist() == [dates[1]]
    assert "MULTI_OBSERVATION_CHANGE" in audit.Reason.to_list()
    assert "CHANGE_LEVEL_MISMATCH" in audit.Reason.to_list()


def copy_inputs(tmp_path):
    paths = [
        "config/contract.yaml",
        "config/curve.yaml",
        "config/project.yaml",
        "config/risk.yaml",
        "outputs/curves/zero_curve_panel.csv",
        "outputs/curves/zero_rate_changes.csv",
        "outputs/curve_validation/selected_method.json",
        "outputs/pricing/irs_mtm_pnl.csv",
        "data/processed/ois_par_rates_wide.csv",
        "data/processed/sofr_fixings.csv",
        "data/processed/sofr_index.csv",
        "src/irs_project/risk/models.py",
        "src/irs_project/risk/rolling.py",
        "src/irs_project/pricing/risk_horizon.py",
        "src/irs_project/pricing/valuation.py",
    ]
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(PROJECT_ROOT / relative, destination)
    return tmp_path


def test_rolling_schema_alignment_future_mutation(tmp_path):
    root = copy_inputs(tmp_path)
    forecasts, diagnostics = run(root, max_dates=3, overrides={"simulations": 200})
    assert forecasts.columns.tolist() == OUTPUT_COLUMNS
    assert len(forecasts) == 18
    assert forecasts.Date.min() == pd.Timestamp("2023-05-31")
    assert (forecasts.Forecast_As_Of < forecasts.Date).all()
    assert diagnostics.Status.eq("SUCCESS").all()
    assert (diagnostics.Window_Count == 500).all()
    assert (diagnostics.Window_End <= diagnostics.Information_Cutoff).all()
    align = pd.read_csv(root / "outputs/risk_smoke/risk_pnl_alignment.csv")
    assert align.Alignment_Status.eq("MATCHED").all()
    cutoff = forecasts.Forecast_As_Of.max()
    for relative in [
        "outputs/curves/zero_curve_panel.csv",
        "outputs/curves/zero_rate_changes.csv",
        "data/processed/ois_par_rates_wide.csv",
        "data/processed/sofr_index.csv",
        "data/processed/sofr_fixings.csv",
    ]:
        frame = pd.read_csv(root / relative, parse_dates=["Date"])
        numeric = frame.select_dtypes(include="number").columns
        frame.loc[frame.Date > cutoff, numeric] *= 10
        frame.to_csv(root / relative, index=False)
    again, _ = run(root, max_dates=3, overrides={"simulations": 200})
    pd.testing.assert_frame_equal(forecasts, again)


def test_missing_cutoff_exports_failure_rows(tmp_path):
    root = copy_inputs(tmp_path)
    path = root / "data/processed/sofr_index.csv"
    frame = pd.read_csv(path)
    frame.loc[frame.Date != "2023-05-30"].to_csv(path, index=False)
    forecasts, diagnostics = run(root, max_dates=1, overrides={"simulations": 200})
    assert len(forecasts) == 6
    assert forecasts[["VaR", "ES"]].isna().all().all()
    assert diagnostics.Status.eq("FAILED").all()
    assert diagnostics.Reason.str.contains("Missing exact cutoff").all()


def test_realized_payment_pnl_matches_existing_engine(inputs):
    cfg, contract, market, history, method = inputs
    pnl = read_dates(PROJECT_ROOT / "outputs/pricing/irs_mtm_pnl.csv")
    for target in pd.to_datetime(["2024-05-03", "2025-05-05", "2026-05-05"]):
        cutoff = pnl.index[pnl.index.get_loc(target) - 1]
        old = price_irs(
            cutoff, curve_from_market_row(market, cutoff, method, cfg), contract, history
        )
        new = price_irs(
            target, curve_from_market_row(market, target, method, cfg), contract, history
        )
        cashflow = _realized_net_cashflow(
            cutoff, target, contract, history, build_payment_schedule(contract)
        )
        assert old.market_value - new.market_value - cashflow == pytest.approx(
            pnl.loc[target, "Loss"], abs=1e-5
        )


def test_final_settlement_and_maturity(inputs):
    from dataclasses import replace

    cfg, contract, market, history, method = inputs
    contract = replace(contract, maturity_date=pd.Timestamp("2026-05-01"))
    cutoff, target = pd.Timestamp("2026-05-04"), pd.Timestamp("2026-05-06")
    curve = curve_from_market_row(market, cutoff, method, cfg)
    pricer = HorizonRepricer(cutoff, target, curve, cfg, contract, history)
    values = pricer.values(np.zeros((2, len(pricer.tenors))))
    np.testing.assert_array_equal(values, [0.0, 0.0])
    assert pricer.cashflow != 0
    assert abs(pricer.losses(np.zeros((1, len(pricer.tenors))))[0]) < 1000


def test_insufficient_window_is_logged(tmp_path):
    root = copy_inputs(tmp_path)
    forecasts, diagnostics = run(root, max_dates=1, overrides={"window": 5000, "simulations": 200})
    assert len(forecasts) == 6
    assert forecasts[["VaR", "ES"]].isna().all().all()
    assert diagnostics.Reason.str.contains("Insufficient valid rolling history").all()
