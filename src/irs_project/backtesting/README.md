# IRS Out-of-Sample Backtesting

This module evaluates existing one-day (1D) USD IRS risk forecasts against realized losses. It aligns the forecast information cutoff to the start of the realized P&L interval, selects a common out-of-sample set, computes VaR coverage tests and an ES calibration diagnostic, and exports model comparisons and an exclusion audit.

The forecasts come from Historical Simulation (HS), exponentially weighted moving average (EWMA), and principal component analysis Monte Carlo (PCA_MC). The runner reads the saved forecasts and mark-to-market P&L without fitting the risk models or rerunning pricing.

## Inputs

| File | Use |
|---|---|
| `outputs/risk/risk_model_outputs.csv` | VaR, ES, forecast horizon and information date for each target date, model and confidence level. |
| `outputs/risk/risk_pnl_alignment.csv` | Information cutoff, prior P&L date, aligned realized loss, alignment status and issue flags for each target date. |
| `outputs/risk/risk_forecast_diagnostics.csv` | Forecast status and original failure reason by target date and model. Each diagnostic applies to both confidence levels. Its cutoff and alignment status are checked against the P&L alignment audit for exclusion classification. |
| `outputs/pricing/irs_mtm_pnl.csv` | Realized loss, total P&L and valuation status. The preceding row in date order supplies the prior pricing date. |

## Data splits and common sample

The splits in `config/project.yaml` use inclusive boundaries.

| Split | Start | End |
|---|---|---|
| Training | 2018-04-02 | 2021-12-31 |
| Validation | 2022-01-03 | 2023-04-28 |
| Inception transition | 2023-05-01 | 2023-05-30 |
| Test | 2023-05-31 | Open-ended |

The checked-in forecasts run through 2026-10-29. The backtest evaluates the test split only.

A valid row has a 1D forecast, finite VaR, ES, loss and P&L, and ES >= VaR >= 0. It requires a SUCCESS or MATURED valuation, MATCHED P&L alignment and a SUCCESS model diagnostic. The loss must agree with both minus total P&L and the aligned realized loss to within USD 0.000001. The forecast as-of date must equal the information cutoff and both prior P&L dates (from pricing and alignment), and precede the target date.

Each candidate date has one forecast for each of the three models at both confidence levels. A date enters the common sample only if all six rows are valid. An invalid forecast excludes the entire date from comparison. The runner requires at least 40 common valid dates.

## VaR backtesting

The 95% and 99% VaR forecasts target the corresponding quantiles of one-day loss, implying expected exceedance rates of 5% and 1%. An exception occurs when realized loss strictly exceeds VaR.

- **Exception Rate** divides the number of exceptions by the number of valid observations.
- **Kupiec POF Test** uses a likelihood ratio to compare the observed exception frequency with the expected rate.
- **Christoffersen Independence Test** uses a likelihood ratio to check whether the probability of an exception depends on the previous exception indicator. Only adjacent valid P&L intervals contribute transitions.
- **Conditional Coverage Test** combines the unconditional coverage and independence likelihood ratios.
- **VaR Pinball Score** measures quantile forecast accuracy using asymmetric absolute loss at the target quantile. Lower scores indicate better accuracy on the same sample and confidence level.

The VaR tests use a 5% significance threshold. Sparse exceptions or transitions can limit the reliability of the asymptotic chi-square p-values.

## ES calibration diagnostic

For confidence level alpha, the ES calibration moment is
`Z_t = max(Loss_t - VaR_t, 0) / (1 - alpha) - (ES_t - VaR_t)`.
Under correct joint VaR and ES calibration, `E[Z_t] = 0`.

The gap-aware circular block bootstrap uses centered calibration moments, a block length of 10 and 2,000 simulations. It samples within contiguous segments without joining blocks across gaps. `ES_Moment_CI_Lower` and `ES_Moment_CI_Upper` bound the 95% confidence interval for the mean of the ES calibration moment. `Mean_ES` separately reports the average ES forecast amount in USD.

The interval is an exploratory unconditional ES calibration diagnostic. It cannot establish conditional calibration or isolate ES error from VaR error. Inference depends on the dependence and stationarity of the moments and can be sensitive to block length. Zero inside the interval indicates that this diagnostic does not detect a nonzero mean. The ES ratio is descriptive.

## Run

From the repository root:

~~~sh
uv run python scripts/run_backtesting.py
uv run pytest
uv run ruff check .
~~~

## Outputs

All paths below are relative to `outputs/backtesting/`.

| Output | Contents |
|---|---|
| `backtest_results.csv` | Full common-sample statistics and decisions by model and confidence level. |
| `model_comparison.csv` | Selected VaR test statistics, forecast averages, ES moment estimates and pinball scores. |
| `model_comparison.md` | Model comparison, coverage, exclusion totals and statistical interpretation. |
| `backtest_detail.csv` | All candidate forecast rows with realized P&L, alignment and forecast diagnostics. |
| `common_sample_detail.csv` | Valid forecast rows on the shared test dates. |
| `excluded_forecasts.csv` | All forecast rows on excluded dates, with the original Reason and Invalid_Reason, alignment evidence, Failure_Category and its explanation. |
| `excluded_date_summary.csv` | Unique excluded dates and excluded forecast rows by category, with totals. |
| `figures/` | Realized loss and VaR charts with exceptions marked for each model and confidence level. |

Failure classification uses the model diagnostic's reason and corroborates it against the P&L alignment record. The categories capture nonbusiness target or cutoff dates, realized P&L interval mismatches, and missing exact cutoff SOFR Index observations. Uncorroborated, unknown or mixed causes are recorded under `OTHER_UNCLASSIFIED` with an explanation. All six forecast rows inherit their date's category, so the date totals and forecast-row totals can be reconciled independently.
