# IRS Backtesting Research Summary

## Research Overview

This study uses historical SOFR market data to evaluate one-day risk forecasts for a USD interest rate swap held by the John Hancock Financial Opportunities Fund. It compares Historical Simulation (HS), Exponentially Weighted Moving Average (EWMA), and PCA Monte Carlo (PCA_MC) at the 95% and 99% confidence levels. Out-of-sample backtests compare Value at Risk (VaR) and Expected Shortfall (ES) forecasts with realized losses from the swap's historical mark-to-market P&L.

## Data and Testing Sample

The test period runs from 2023-05-31 through 2026-10-29. Of 877 candidate dates, all three models use the same 830 valid dates at both confidence levels. This holds market conditions and realized losses fixed across models. The common-sample screen excludes 47 dates and 282 forecast rows.

| Failure Category | Dates | Forecast Rows |
|---|---:|---:|
| Non-business forecast or cutoff date | 30 | 180 |
| Realized P&L interval mismatch | 16 | 96 |
| Missing exact cutoff SOFR Index | 1 | 6 |
| Other | 0 | 0 |
| **Total** | 47 | 282 |

## VaR Backtesting Results

The expected exception rates are 5% and 1% at the 95% and 99% VaR levels, respectively. An exception occurs when realized loss exceeds forecast VaR. The table reports p-values for Kupiec's unconditional coverage test, Christoffersen's independence test, and the combined conditional coverage test.

| Model | VaR Level | Exceptions | Exception Rate | Kupiec p | Christoffersen Independence p | Conditional Coverage p |
|---|---:|---:|---:|---:|---:|---:|
| HS | 95% | 22 | 2.65% | 0.000676155 | 0.289363 | 0.00176761 |
| EWMA | 95% | 36 | 4.34% | 0.370582 | 0.697049 | 0.620869 |
| PCA_MC | 95% | 17 | 2.05% | 1.05499e-05 | 0.421391 | 4.41552e-05 |
| HS | 99% | 5 | 0.60% | 0.213866 | 0.823117 | 0.450447 |
| EWMA | 99% | 12 | 1.45% | 0.226245 | 0.564065 | 0.407174 |
| PCA_MC | 99% | 6 | 0.72% | 0.398622 | 0.764033 | 0.669452 |

At the 5% significance level, conditional coverage rejects HS and PCA_MC at 95% VaR. Both produced substantially fewer exceptions than the 5% target implies, consistent with conservative VaR forecasts in this sample. The test does not reject EWMA. At 99% VaR, conditional coverage does not reject any model. The 5, 12, and 6 exceptions for HS, EWMA, and PCA_MC, respectively, limit the power of those tests. Failure to reject leaves model adequacy uncertain.

## Expected Shortfall Calibration

For realized loss $L_t$ and forecast confidence level $\alpha$, the ES calibration moment is

$$
Z_t = \frac{\max(L_t - \mathrm{VaR}_t, 0)}{1 - \alpha}
      - (\mathrm{ES}_t - \mathrm{VaR}_t).
$$

Under correct joint VaR and ES calibration, $\mathbb{E}[Z_t]=0$. Mean ES is the average forecast ES amount. The moment mean is the sample average of $Z_t$. The 95% confidence intervals estimate that moment mean, while the table's Mean ES column reports forecast amounts. All amounts are in USD.

The primary basic (pivotal) interval subtracts the 97.5th and 2.5th quantiles of the centered bootstrap means from the sample mean. The equal-tailed p-value for a zero mean doubles the smaller tail probability on the same interpolated quantile grid. Ties are included on both sides, and the tail probability has a Monte Carlo floor of 1/(B + 1) for B draws. The gap-aware circular bootstrap uses the same block length (10), 2,000 simulations and seed (5003) for all groups. The original symmetric interval and absolute-tail p-value remain available as sensitivity diagnostics.

| Model | ES Level | Mean ES | ES Calibration Moment Mean | Pivotal 95% CI | Equal-tailed p | Zero in CI |
|---|---:|---:|---:|---|---:|:---:|
| HS | 95% | 51,708.33 | -10,699.12 | [-14,759.24, -7,018.41] | 0.0009995 | No |
| EWMA | 95% | 36,109.73 | 2,629.41 | [-2,879.01, 6,942.79] | 0.304914 | Yes |
| PCA_MC | 95% | 44,975.66 | -3,645.62 | [-7,703.36, -415.10] | 0.020949 | No |
| HS | 99% | 78,239.76 | -11,273.62 | [-18,374.10, -6,428.83] | 0.0009995 | No |
| EWMA | 99% | 46,685.99 | 15,941.76 | [-738.47, 29,510.29] | 0.0586224 | Yes |
| PCA_MC | 99% | 58,157.06 | 2,781.40 | [-6,965.46, 10,324.80] | 0.508363 | Yes |

For EWMA at 99%, zero lies in the pivotal interval [-738.47, 29,510.29] (p = 0.0586224). The symmetric interval [1,193.23, 30,690.29] excludes zero (absolute-tail p = 0.035982). The remaining groups have the same zero-inclusion decision under both constructions. The moment depends on VaR, so departures can reflect errors in either forecast.

## Overall Findings

EWMA's 95% VaR exception rate is the closest to its target, and its 95% ES diagnostic is compatible with a zero mean. At 99%, the limited tail observations prevent a reliable ranking by VaR coverage. The ES results add information about tail calibration and vary across levels, so the evidence supports conclusions specific to each metric and confidence level.

## Short-Segment Sensitivity

The common sample splits into 25 contiguous segments. Three segments have fewer than 10 observations (lengths 8, 9, and 9). A segment of size m is selected with probability m/830 per block, then contributes at most min(m, 10) observations. Accounting for the truncated final block, the short segments comprise 3.13% of the original sample and 2.74% of expected bootstrap observations. The implied offsets in expected bootstrap mean on this sample range from USD 3.59 to USD 83.95 across the six groups.

A sensitivity run sampled segments in proportion to their lengths divided by the available block size, including the final truncated block. This restores observation-proportional weight in expectation. With 2,000 draws, all six pivotal zero-inclusion decisions were unchanged. EWMA at 99% remains sensitive to the interval construction, while this weighting check supports keeping the original block sampler for this dataset.

## Limitations

The findings reflect one USD IRS position and the observed market period. Sparse 99% VaR exceptions limit test power. The gap-aware block bootstrap is sensitive to block length and assumptions about stationarity and temporal dependence. It provides an exploratory unconditional ES calibration diagnostic. A conditional ES assessment would require additional tests.

Results: [VaR comparison](../../../outputs/backtesting/model_comparison.csv) · [Full backtest statistics](../../../outputs/backtesting/backtest_results.csv) · [Exclusion summary](../../../outputs/backtesting/excluded_date_summary.csv)

Reproduce from the repository root with `uv run python scripts/run_backtesting.py`.
