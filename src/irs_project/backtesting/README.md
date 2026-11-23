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

Under correct joint VaR and ES calibration, $\mathbb{E}[Z_t]=0$. Mean ES is the average forecast ES amount. The moment mean is the sample average of $Z_t$, and the 95% bootstrap interval estimates that moment mean. All amounts in the table are in USD.

| Model | ES Level | Mean ES | ES Calibration Moment Mean | ES Calibration Moment 95% CI | Bootstrap p | Zero in CI |
|---|---:|---:|---:|---:|---:|:---:|
| HS | 95% | 51,707.35 | -10,697.52 | [-14,505.86, -6,889.17] | 0.00049975 | No |
| EWMA | 95% | 36,111.09 | 2,627.97 | [-2,271.76, 7,527.71] | 0.296852 | Yes |
| PCA_MC | 95% | 44,975.90 | -3,645.73 | [-7,181.74, -109.72] | 0.043978 | No |
| HS | 99% | 78,230.25 | -11,266.10 | [-16,918.14, -5,614.07] | 0.003998 | No |
| EWMA | 99% | 46,687.74 | 15,938.52 | [1,191.31, 30,685.73] | 0.035982 | No |
| PCA_MC | 99% | 58,157.38 | 2,779.60 | [-5,729.26, 11,288.45] | 0.547726 | Yes |

At 95%, the interval contains zero for EWMA and lies below zero for HS and PCA_MC. At 99%, it contains zero for PCA_MC, lies below zero for HS, and lies above zero for EWMA. Intervals excluding zero provide evidence of a nonzero unconditional moment under the bootstrap assumptions. Intervals containing zero are compatible with a zero moment. The moment also depends on VaR, so departures can reflect errors in either forecast.

## Overall Findings

EWMA's 95% VaR exception rate is the closest to its target, and its 95% ES diagnostic is compatible with a zero mean. At 99%, the limited tail observations prevent a reliable ranking by VaR coverage. The ES results add information about tail calibration and vary across levels, so the evidence supports conclusions specific to each metric and confidence level.

## Limitations

The findings reflect one USD IRS position and the observed market period. Sparse 99% VaR exceptions limit test power. The gap-aware block bootstrap is sensitive to block length and assumptions about stationarity and temporal dependence. It provides an exploratory unconditional ES calibration diagnostic. A conditional ES assessment would require additional tests.

Results: [VaR comparison](../../../outputs/backtesting/model_comparison.csv) · [Full backtest statistics](../../../outputs/backtesting/backtest_results.csv) · [Exclusion summary](../../../outputs/backtesting/excluded_date_summary.csv)

Reproduce from the repository root with `uv run python scripts/run_backtesting.py`.
