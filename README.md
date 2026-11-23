# USD SOFR Swap Pricing and Risk Backtesting

CUHK RMSC5003 group research on a USD 10 million pay-fixed, receive-compounded-SOFR interest rate swap held by the John Hancock Financial Opportunities Fund. Using historical Bloomberg market data, we built daily SOFR curves, valued the swap, and compared three one-day risk forecasts against cashflow-adjusted mark-to-market losses.

## Main Findings

- **Curve selection.** Monotone-convex forward interpolation had the lowest leave-one-tenor-out RMSE in both training and validation. The selected method was fixed before the out-of-sample comparison.
- **95% VaR.** EWMA came closest to the 5% target exception rate. Its conditional coverage test did not reject at the 5% significance level. Historical Simulation and PCA Monte Carlo produced fewer exceptions than expected, consistent with conservative VaR forecasts in this sample, and both were rejected.
- **99% VaR.** The conditional coverage test did not reject any of the three models. With only 5 to 12 exceptions per model, the sample offers limited power to distinguish their coverage.
- **Expected Shortfall.** The bootstrap interval for the mean ES calibration moment contains zero for EWMA at 95% and PCA Monte Carlo at 99%. The diagnostic measures unconditional calibration and depends on both VaR and ES.

## Study Design and Sample

Historical Simulation (HS), Exponentially Weighted Moving Average (EWMA), and PCA Monte Carlo (PCA_MC) use the same contract, pricing engine, and P&L definition. The out-of-sample evaluation runs from **2023-05-31 to 2026-10-29**. All models and confidence levels use the same **830 valid dates** out of 877 candidates. The common-sample screen excludes 47 dates and 282 forecast rows.

| Failure Category | Dates | Forecast Rows |
|---|---:|---:|
| Non-business forecast or cutoff date | 30 | 180 |
| Realized P&L interval mismatch | 16 | 96 |
| Missing exact cutoff SOFR Index | 1 | 6 |
| Other | 0 | 0 |
| **Total** | 47 | 282 |

## Value at Risk Results

The expected exception rates are 5% at 95% VaR and 1% at 99% VaR. An exception occurs when realized loss exceeds predicted VaR.

| Model | VaR Level | Exceptions | Exception Rate | Kupiec p | Christoffersen Independence p | Conditional Coverage p |
|---|---:|---:|---:|---:|---:|---:|
| HS | 95% | 22 | 2.65% | 0.000676155 | 0.289363 | 0.00176761 |
| EWMA | 95% | 36 | 4.34% | 0.370582 | 0.697049 | 0.620869 |
| PCA_MC | 95% | 17 | 2.05% | 1.05499e-05 | 0.421391 | 4.41552e-05 |
| HS | 99% | 5 | 0.60% | 0.213866 | 0.823117 | 0.450447 |
| EWMA | 99% | 12 | 1.45% | 0.226245 | 0.564065 | 0.407174 |
| PCA_MC | 99% | 6 | 0.72% | 0.398622 | 0.764033 | 0.669452 |

![Realized loss and EWMA 95% VaR on the common test sample](outputs/backtesting/figures/EWMA_95_var.png)

## Expected Shortfall Results

Mean ES is the average forecasted tail loss in USD. The ES calibration moment has a theoretical mean of zero under correct joint VaR and ES calibration. The 95% block-bootstrap confidence interval estimates the mean of this moment.

| Model | ES Level | Mean ES | ES Calibration Moment Mean | ES Calibration Moment 95% CI | Bootstrap p | Zero in CI |
|---|---:|---:|---:|---:|---:|:---:|
| HS | 95% | 51,707.35 | -10,697.52 | [-14,505.86, -6,889.17] | 0.00049975 | No |
| EWMA | 95% | 36,111.09 | 2,627.97 | [-2,271.76, 7,527.71] | 0.296852 | Yes |
| PCA_MC | 95% | 44,975.90 | -3,645.73 | [-7,181.74, -109.72] | 0.043978 | No |
| HS | 99% | 78,230.25 | -11,266.10 | [-16,918.14, -5,614.07] | 0.003998 | No |
| EWMA | 99% | 46,687.74 | 15,938.52 | [1,191.31, 30,685.73] | 0.035982 | No |
| PCA_MC | 99% | 58,157.38 | 2,779.60 | [-5,729.26, 11,288.45] | 0.547726 | Yes |

At 95%, the intervals for HS and PCA_MC lie below zero. At 99%, the HS interval lies below zero and the EWMA interval lies above zero. These departures provide evidence of a nonzero mean under the bootstrap assumptions. Conclusions apply to this swap and sample period. Sparse 99% VaR exceptions limit inference, and the exploratory ES diagnostic is sensitive to block length and time-series dependence.

## Research Outputs

| Area | Results |
|---|---|
| SOFR curve construction | [Method selection and validation](outputs/curve_validation/final_method_recommendation.md) · [Daily zero curves](outputs/curves/zero_curve_panel.csv) |
| IRS valuation | [Daily mark-to-market and P&L](outputs/pricing/irs_mtm_pnl.csv) · [Contract and pricing methodology](docs/irs_pricing_methodology.md) |
| Risk forecasting | [Rolling VaR and ES forecasts](outputs/risk/risk_model_outputs.csv) · [Risk integration validation](outputs/risk/risk_validation_report.md) |
| Backtesting | [Research summary](src/irs_project/backtesting/README.md) · [Full statistics](outputs/backtesting/backtest_results.csv) · [Exclusion audit](outputs/backtesting/excluded_date_summary.csv) |

## Contributions

- **陈美婷** developed the HS, EWMA, and PCA Monte Carlo risk forecasts.
- **Faye Sun** ([@fayeyeye](https://github.com/fayeyeye)) implemented the initial VaR and ES backtesting and model comparison in [PR #4](https://github.com/rOOOOOnn/IRS/pull/4).
- **Ron** developed the data, curve construction, and IRS pricing workflows and finalized the Backtesting integration.

For reproduction, see [environment setup](docs/environment_setup.md). The backtest can be reproduced from the checked-in inputs with `uv run python scripts/run_backtesting.py`.
