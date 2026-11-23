# IRS Out-of-Sample Backtesting & Model Comparison

All results use the fixed common test sample.

Candidate dates: **877**, common valid dates: **830**, excluded dates: **47**.

## VaR Coverage and ES Calibration

### 95% Confidence Level

| Model | N | Exceptions | Rate | Kupiec p | IND p | CC p | Mean VaR | Mean ES | Pinball |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EWMA | 830 | 36 | 4.34% | 0.3706 | 0.6970 | 0.6209 | 28,770.1726 | 36,109.7328 | 1,963.5544 |
| HS | 830 | 22 | 2.65% | 0.0007 | 0.2894 | 0.0018 | 35,100.2760 | 51,708.3315 | 2,077.0577 |
| PCA_MC | 830 | 17 | 2.05% | 0.0000 | 0.4214 | 0.0000 | 35,836.9121 | 44,975.6596 | 2,093.0991 |

Expected exceedance rate: 5%.

### 99% Confidence Level

| Model | N | Exceptions | Rate | Kupiec p | IND p | CC p | Mean VaR | Mean ES | Pinball |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EWMA | 830 | 12 | 1.45% | 0.2262 | 0.5641 | 0.4072 | 40,738.6982 | 46,685.9922 | 631.5970 |
| HS | 830 | 5 | 0.60% | 0.2139 | 0.8231 | 0.4504 | 62,163.6114 | 78,239.7557 | 674.9808 |
| PCA_MC | 830 | 6 | 0.72% | 0.3986 | 0.7640 | 0.6695 | 50,726.1864 | 58,157.0602 | 614.7040 |

Expected exceedance rate: 1%.

## ES Calibration Moment 95% CI

The primary interval is asymmetric and pivotal. Its equal-tailed p-value tests whether the mean moment is zero. The symmetric interval and absolute-tail p-value use the same centered draws and show sensitivity to the inference method.

| Model | Level | Moment mean | Pivotal CI | Equal-tailed p | Zero in pivotal CI | Symmetric CI | Absolute-tail p | Zero in symmetric CI |
|---|---:|---:|---|---:|:---:|---|---:|:---:|
| EWMA | 95% | 2,629.4095 | [-2,879.0106, 6,942.7950] | 0.304914 | Yes | [-2,269.9906, 7,528.8097] | 0.296852 | Yes |
| EWMA | 99% | 15,941.7601 | [-738.4729, 29,510.2941] | 0.0586224 | Yes | [1,193.2294, 30,690.2908] | 0.035982 | No |
| HS | 95% | -10,699.1238 | [-14,759.2353, -7,018.4120] | 0.0009995 | No | [-14,507.6008, -6,890.6469] | 0.00049975 | No |
| HS | 99% | -11,273.6245 | [-18,374.1002, -6,428.8307] | 0.0009995 | No | [-16,925.6710, -5,621.5780] | 0.003998 | No |
| PCA_MC | 95% | -3,645.6241 | [-7,703.3574, -415.1025] | 0.020949 | No | [-7,181.8468, -109.4015] | 0.043978 | No |
| PCA_MC | 99% | 2,781.3977 | [-6,965.4604, 10,324.8000] | 0.508363 | Yes | [-5,729.0414, 11,291.8368] | 0.547226 | Yes |

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
