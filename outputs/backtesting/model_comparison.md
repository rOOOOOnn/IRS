# IRS Out-of-Sample Backtesting & Model Comparison

All results use the fixed common test sample.

Candidate dates: **877**, common valid dates: **830**, excluded dates: **47**.

## VaR Coverage and ES Calibration

### 95% Confidence Level

| Model | N | Exceptions | Rate | Kupiec p | IND p | CC p | Mean VaR | Mean ES | ES Calibration Moment 95% CI | Pinball |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| EWMA | 830 | 36 | 4.34% | 0.3706 | 0.6970 | 0.6209 | 28,771.1946 | 36,111.0924 | [-2,271.7640, 7,527.7126] | 1,963.4891 |
| HS | 830 | 22 | 2.65% | 0.0007 | 0.2894 | 0.0018 | 35,101.5677 | 51,707.3527 | [-14,505.8635, -6,889.1728] | 2,077.0275 |
| PCA_MC | 830 | 17 | 2.05% | 0.0000 | 0.4214 | 0.0000 | 35,837.3366 | 44,975.9014 | [-7,181.7399, -109.7216] | 2,093.0443 |

Expected exceedance rate: 5%.

### 99% Confidence Level

| Model | N | Exceptions | Rate | Kupiec p | IND p | CC p | Mean VaR | Mean ES | ES Calibration Moment 95% CI | Pinball |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| EWMA | 830 | 12 | 1.45% | 0.2262 | 0.5641 | 0.4072 | 40,740.2004 | 46,687.7431 | [1,191.3091, 30,685.7332] | 631.5698 |
| HS | 830 | 5 | 0.60% | 0.2139 | 0.8231 | 0.4504 | 62,162.5033 | 78,230.2508 | [-16,918.1431, -5,614.0659] | 674.9486 |
| PCA_MC | 830 | 6 | 0.72% | 0.3986 | 0.7640 | 0.6695 | 50,726.7461 | 58,157.3793 | [-5,729.2569, 11,288.4538] | 614.6769 |

Expected exceedance rate: 1%.

## Excluded-Date Diagnostics

A date is excluded from the common sample if any forecast fails. Each excluded date and all of its forecast rows share one category. Model diagnostic reasons are checked against P&L alignment flags.
Failed model diagnostics linked to exclusions: **141** (unique date/model pairs).

| Failure Category | Unique Excluded Dates | Excluded Forecast Rows |
|---|---:|---:|
| NON_BUSINESS_FORECAST_OR_CUTOFF_DATE | 30 | 180 |
| REALIZED_PNL_INTERVAL_MISMATCH | 16 | 96 |
| MISSING_EXACT_CUTOFF_SOFR_INDEX | 1 | 6 |
| OTHER_UNCLASSIFIED | 0 | 0 |
| TOTAL | 47 | 282 |

## Statistical Interpretation and Limitations

- A p-value >= 0.05 means failure to reject, not proof that the model is correct.
- Christoffersen uses consecutive valid intervals only.
- Sparse exceedances can weaken chi-square approximations.
- The ES calibration moment is `max(Loss - VaR, 0) / (1 - alpha) - (ES - VaR)`. Its expected value is zero under correct joint VaR and ES calibration.
- Mean ES averages the ES forecasts in USD. The 95% bootstrap interval estimates the mean of the ES calibration moment. These describe different quantities.
- The gap-aware circular block bootstrap provides an exploratory unconditional ES calibration diagnostic. It cannot establish conditional ES calibration.
- Bootstrap inference assumes sufficiently stationary and weakly dependent residuals.
- Bootstrap results may depend on block length.
- The ES Ratio is descriptive, not a standalone formal statistical test.
- Pinball Score measures VaR quantile accuracy.
- All model comparisons use the same dates.
- No model parameters were recalibrated.

## Figures

Rolling Loss vs VaR figures are saved under `outputs/backtesting/figures/`.
