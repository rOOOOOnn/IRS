# Financial and Numerical Audit — Current IRS Contract

## Scope and current value

The current contract in [config/contract.yaml](../config/contract.yaml) uses semiannual fixed
payments and quarterly compounded SOFR payments. The research terms use Actual/360, Modified
Following on the US Government Bond calendar, a two-business-day payment lag and ex-cashflow
valuation. The USD 10 million notional and 3.356% fixed rate are disclosed terms. The
effective date 2023-05-01 and maturity date 2028-05-01
are research assumptions.

The initial valuation was independently reconciled by summing discounted scheduled coupons for
each of the four saved curves. The fixed amount uses notional times fixed rate times accrual days
over 360. The inception floating amount uses the curve's accrual-start discount factor divided by
its accrual-end discount factor, less one, times notional. Both legs discount to their respective
payment dates. Market value is floating PV minus fixed PV, computed before rounding.

| Interpolation | Fixed PV (USD) | Floating PV (USD) | IRS market value (USD) |
|---|---:|---:|---:|
| linear_zero | 1,538,104.53 | 1,567,118.02 | 29,013.49 |
| log_linear_discount | 1,538,647.56 | 1,567,066.75 | 28,419.18 |
| natural_cubic_zero | 1,538,431.84 | 1,567,045.93 | 28,614.09 |
| monotone_convex_forward | 1,538,468.33 | 1,567,044.46 | 28,576.12 |

The selected curve is monotone-convex forward. The annual-payment reconstruction in the
[archived audit](https://github.com/rOOOOOnn/IRS/blob/8638fdbc040614a9ffc6d16bcd3cccb1065a8ca7/outputs/FINANCIAL_AUDIT_REPORT.md)
reported USD 41,392.94. The disclosed payment frequencies supersede that historical value.
The curve selection and calibration methodology are documented in the
[curve validation report](curve_validation/final_method_recommendation.md).

## Initial cashflow schedule

Amounts are undiscounted USD. Floating amounts are forecasts as of inception.

| Leg | Accrual start | Accrual end | Payment date | Amount (USD) |
|---|---|---|---|---:|
| Fixed | 2023-05-01 | 2023-11-01 | 2023-11-03 | 171,528.89 |
| Fixed | 2023-11-01 | 2024-05-01 | 2024-05-03 | 169,664.44 |
| Fixed | 2024-05-01 | 2024-11-01 | 2024-11-05 | 171,528.89 |
| Fixed | 2024-11-01 | 2025-05-01 | 2025-05-05 | 168,732.22 |
| Fixed | 2025-05-01 | 2025-11-03 | 2025-11-05 | 173,393.33 |
| Fixed | 2025-11-03 | 2026-05-01 | 2026-05-05 | 166,867.78 |
| Fixed | 2026-05-01 | 2026-11-02 | 2026-11-04 | 172,461.11 |
| Fixed | 2026-11-02 | 2027-05-03 | 2027-05-05 | 169,664.44 |
| Fixed | 2027-05-03 | 2027-11-01 | 2027-11-03 | 169,664.44 |
| Fixed | 2027-11-01 | 2028-05-01 | 2028-05-03 | 169,664.44 |
| Floating | 2023-05-01 | 2023-08-01 | 2023-08-03 | 130,611.93 |
| Floating | 2023-08-01 | 2023-11-01 | 2023-11-03 | 129,522.48 |
| Floating | 2023-11-01 | 2024-02-01 | 2024-02-05 | 120,264.09 |
| Floating | 2024-02-01 | 2024-05-01 | 2024-05-03 | 108,143.49 |
| Floating | 2024-05-01 | 2024-08-01 | 2024-08-05 | 97,565.16 |
| Floating | 2024-08-01 | 2024-11-01 | 2024-11-05 | 85,155.98 |
| Floating | 2024-11-01 | 2025-02-03 | 2025-02-05 | 81,415.80 |
| Floating | 2025-02-03 | 2025-05-01 | 2025-05-05 | 74,779.99 |
| Floating | 2025-05-01 | 2025-08-01 | 2025-08-05 | 75,906.51 |
| Floating | 2025-08-01 | 2025-11-03 | 2025-11-05 | 75,396.04 |
| Floating | 2025-11-03 | 2026-02-02 | 2026-02-04 | 72,547.98 |
| Floating | 2026-02-02 | 2026-05-01 | 2026-05-05 | 70,307.72 |
| Floating | 2026-05-01 | 2026-08-03 | 2026-08-05 | 75,295.43 |
| Floating | 2026-08-03 | 2026-11-02 | 2026-11-04 | 72,686.77 |
| Floating | 2026-11-02 | 2027-02-01 | 2027-02-03 | 72,660.86 |
| Floating | 2027-02-01 | 2027-05-03 | 2027-05-05 | 72,977.71 |
| Floating | 2027-05-03 | 2027-08-02 | 2027-08-04 | 73,743.29 |
| Floating | 2027-08-02 | 2027-11-01 | 2027-11-03 | 74,121.08 |
| Floating | 2027-11-01 | 2028-02-01 | 2028-02-03 | 75,332.38 |
| Floating | 2028-02-01 | 2028-05-01 | 2028-05-03 | 74,081.38 |

## SOFR carry on dates without an exact Index

A published Index ratio supplies realized accrual up to its anchor date. The anchor-date curve
projects elapsed carry using the reciprocal discount factor to valuation. The valuation-date
curve then projects the remaining coupon. The projected values are valuation-only and do not
enter the published Index series or settled-coupon accounting.

| Valuation date | Published Index date | Elapsed carry factor | Added accrued floating (USD) | Previous MTM (USD) | Revised MTM (USD) |
|---|---|---:|---:|---:|---:|
| 2023-11-23 | 2023-11-22 | 1.000147891 | 1,483.51 | 330,717.66 | 332,200.28 |
| 2024-06-19 | 2024-06-18 | 1.000148291 | 1,493.46 | 279,882.14 | 281,374.72 |
| 2024-11-28 | 2024-11-27 | 1.000126601 | 1,270.27 | 172,466.38 | 173,736.34 |
| 2025-06-19 | 2025-06-18 | 1.000119950 | 1,206.40 | 78,158.80 | 79,364.63 |
| 2025-11-11 | 2025-11-10 | 1.000110641 | 1,107.27 | -9,263.54 | -8,156.50 |
| 2025-11-27 | 2025-11-26 | 1.000108389 | 1,086.63 | -29,547.08 | -28,460.67 |
| 2026-04-03 | 2026-04-02 | 1.000101534 | 1,021.44 | -23,340.53 | -22,319.50 |
| 2026-06-19 | 2026-06-18 | 1.000100528 | 1,010.12 | 120,598.08 | 121,608.00 |

## Daily P&L reconciliation

All 882 selected-method valuation dates remain in the series. Settled cashflows independently
reconcile to the fixed and floating payment schedules and are unchanged. The carry correction
changes MTM on 8 dates and shifts P&L between each corrected date and the next observation.
The terminal cumulative P&L is USD 554,351.98. It reconciles to the
change in market value since inception plus cumulative settled cashflows, and matches the previous
series at the final date.

- [Four-method valuation panel and carry audit](pricing/irs_mtm_by_method.csv)
- [Selected-method daily attribution](pricing/irs_mtm_pnl.csv)
- [IRS pricing methodology](../docs/irs_pricing_methodology.md)
