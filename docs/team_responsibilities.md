# Team Responsibilities

## 陈美婷 — Risk Modelling

Owns Historical Simulation, EWMA, and PCA-based Monte Carlo. Responsibilities include volatility and covariance estimation, scenario generation, VaR and Expected Shortfall, model comparison, and standardized forecasts.

Primary output: `risk_model_outputs.csv` with `Date`, `Model`, `Confidence_Level`, `Forecast_Horizon`, `VaR`, `ES`, and `Forecast_As_Of`.

Working directory: `src/irs_project/risk/`.

## Faye — Backtesting

Owns VaR and ES backtesting, realized P&L comparison, Kupiec POF testing, Christoffersen independence testing when applicable, performance comparison, and visualizations.

Inputs: `risk_model_outputs.csv`, `ensemble_outputs.csv`, and `irs_mtm_pnl.csv`. Primary output: `backtest_results.csv`.

Working directory: `src/irs_project/backtesting/`.

## Ron — Data, Curve, Pricing, and Ensemble

### Phase 1

- Inspect and preprocess data.
- Assess data quality and historical definitions.
- Maintain project structure, shared configuration, and interfaces.
- Coordinate chronological datasets and handoffs.

### Phase 2

- Construct and calibrate yield curves.
- Implement bootstrapping and interpolation.
- Price the IRS and calculate daily mark-to-market and P&L.

### Phase 3

- Combine HS, EWMA, and PCA-MC forecasts.
- Design dynamic weights and a decision-tree weighting framework.
- Compare the ensemble with individual models.

Primary outputs: `zero_curve_panel.csv`, `discount_factor_panel.csv`, `irs_mtm_pnl.csv`, and `ensemble_outputs.csv`.

Working directories: `src/irs_project/data/`, `curves/`, `pricing/`, and `ensemble/`.

## Shared Rules

- Validate input schemas before calculation.
- Use only information available by the forecast date.
- Update `docs/data_interfaces.md` when an interface changes.
- Never use the test set for model, hyperparameter, or ensemble selection.
