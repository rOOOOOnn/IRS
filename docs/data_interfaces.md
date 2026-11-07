# Data Interfaces

## End-to-End Flow

```text
Market Quotes
-> Preprocessed Market Data
-> Daily Zero Curve
-> IRS Daily MTM and P&L
-> Individual Risk Forecasts
-> Ensemble Forecasts
-> Backtesting
```

All dates use `YYYY-MM-DD`. Rates and confidence levels are decimals unless explicitly stated otherwise. VaR and ES are positive loss magnitudes. P&L is positive for profit and negative for loss.

## Ron to 陈美婷 — `zero_curve_panel.csv`

Fields: `Date`, `Zero_1M`, `Zero_3M`, `Zero_6M`, `Zero_1Y`, `Zero_2Y`, `Zero_3Y`, `Zero_4Y`, `Zero_5Y`.

Risk models should use daily zero-rate changes. Until the curve engine exists, par-rate changes may be used only for a clearly labelled `PROVISIONAL_PAR_RATE_PROXY` prototype.

## Ron to Faye — `irs_mtm_pnl.csv`

Fields: `Date`, `IRS_Market_Value`, `Daily_PnL`, `Cumulative_PnL`, `Loss`, `Valuation_Status`.

- `Daily_PnL = V_t - V_(t-1)`
- `Loss = -Daily_PnL`

## 陈美婷 to Ron and Faye — `risk_model_outputs.csv`

Fields: `Date`, `Model`, `Confidence_Level`, `Forecast_Horizon`, `VaR`, `ES`, `Forecast_As_Of`.

One row represents one model, confidence level, horizon, and forecast date. `Forecast_As_Of` cannot be later than the information set used by the forecast.

## Ron to Faye — `ensemble_outputs.csv`

Fields: `Date`, `Ensemble_VaR`, `Ensemble_ES`, `Weight_HS`, `Weight_EWMA`, `Weight_PCA_MC`, `Market_Regime`.

Weights must sum to one within a documented tolerance. The ensemble rule must be fixed before final test evaluation.

## Phase 1 Market Data Interfaces

- `ois_quotes_long.csv`: one OIS quote per `Date` and `Ticker`.
- `ois_par_rates_wide.csv`: one date per row and one OIS tenor per column.
- `sofr_fixings.csv`: overnight SOFR only.
- `sofr_index.csv`: cumulative SOFR Index values only.
- `data_coverage.csv`: coverage and quality statistics by series.
- `data_manifest.csv`: raw-file provenance and processing status.

No future model output is fabricated in Phase 1.
