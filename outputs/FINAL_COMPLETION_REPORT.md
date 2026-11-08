# Final Completion Report

- Selected global interpolation method: `monotone_convex_forward`.
- Selection used Validation interior-node LOTO RMSE; Test results were excluded from method selection.
- Initial selected-method IRS market value: USD 41,392.94.
- Successful selected-method P&L dates: 882.
- Four-method valuation failures: 0.
- Regime-dependent switching remains diagnostic rather than primary to avoid artificial MTM jumps.
- Contract dates and undisclosed cash-flow conventions remain explicit assumptions in `config/contract.yaml`.
- `zero_curve_panel.csv`, `zero_rate_changes.csv`, and the scenario repricing interface are ready for Member A.
- `irs_mtm_pnl.csv` is ready for Member B.

## Method Comparison

| Method | Dataset | MAE_bps | RMSE_bps | Median_AE_bps | P95_AE_bps | Max_AE_bps | Sample_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| linear_zero | INCEPTION_TRANSITION | 6.760529 | 8.351462 | 4.669259 | 19.232359 | 21.883958 | 168.0 |
| linear_zero | TEST | 3.623957 | 5.123901 | 2.517469 | 11.162328 | 25.866344 | 6888.0 |
| linear_zero | TRAINING | 1.835569 | 2.614079 | 1.233857 | 6.083537 | 17.367681 | 7714.0 |
| linear_zero | VALIDATION | 7.275403 | 9.882878 | 4.724187 | 21.972121 | 40.057259 | 2679.0 |
| log_linear_discount | INCEPTION_TRANSITION | 9.971984 | 16.001555 | 3.128133 | 38.892593 | 41.129747 | 168.0 |
| log_linear_discount | TEST | 5.415466 | 8.58367 | 2.668327 | 20.484512 | 41.306472 | 6888.0 |
| log_linear_discount | TRAINING | 3.017194 | 4.318268 | 1.998211 | 9.096564 | 21.861544 | 7714.0 |
| log_linear_discount | VALIDATION | 8.179561 | 12.702279 | 2.764815 | 27.755401 | 44.945939 | 2679.0 |
| monotone_convex_forward | INCEPTION_TRANSITION | 1.915895 | 3.084473 | 0.51558 | 7.172059 | 8.833305 | 168.0 |
| monotone_convex_forward | TEST | 1.090797 | 1.920992 | 0.436756 | 3.969161 | 11.801101 | 6888.0 |
| monotone_convex_forward | TRAINING | 0.669096 | 1.006101 | 0.406275 | 2.223932 | 12.604782 | 7714.0 |
| monotone_convex_forward | VALIDATION | 2.49418 | 4.085959 | 0.824682 | 9.526708 | 16.966633 | 2679.0 |
| natural_cubic_zero | INCEPTION_TRANSITION | 2.403647 | 3.236427 | 1.739356 | 6.910451 | 9.113356 | 168.0 |
| natural_cubic_zero | TEST | 1.358535 | 2.14872 | 0.768579 | 4.865746 | 11.010767 | 6888.0 |
| natural_cubic_zero | TRAINING | 0.956877 | 1.812033 | 0.438302 | 3.889865 | 27.77397 | 7714.0 |
| natural_cubic_zero | VALIDATION | 4.268925 | 6.861767 | 1.345201 | 15.728232 | 27.011884 | 2679.0 |

## IRS Pricing Impact by Method

| Method | Mean_Absolute_Difference | Max_Absolute_Difference |
| --- | --- | --- |
| linear_zero | 1651.4 | 4646.23 |
| log_linear_discount | 492.37 | 1972.3 |
| monotone_convex_forward | 0.0 | 0.0 |
| natural_cubic_zero | 362.91 | 3562.15 |
