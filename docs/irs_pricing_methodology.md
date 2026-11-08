# IRS Pricing Methodology

## Position and Valuation Basis

The research contract is pay fixed / receive compounded SOFR, so:

```text
Market Value = PV Floating - PV Fixed
```

The engine uses an ex-cashflow value. A settled coupon is removed from market value and included once
in `Net_Cashflow`, preventing payment-date double counting.

## Fixed Leg

The fixed leg uses the configured annual schedule, Actual/360 accrual fractions, payment lag, and
business-day adjustment:

```text
PV Fixed = Notional × Fixed Rate × sum(Accrual Fraction × Discount Factor)
```

## Compounded SOFR Leg

- Fully realized accrual periods use the ratio of SOFR Index values.
- A partially realized period combines the realized SOFR Index factor through the valuation date
  with the current curve's forecast factor for the remaining period.
- Fully future periods use the single-curve discount-factor ratio.
- The engine never reads a realized SOFR observation after the valuation date.

The project deliberately uses one SOFR OIS curve for both projection and discounting. Observation
lookback, shift, lockout, calendar, payment lag, and day count remain editable assumptions in
`config/contract.yaml`.

## Daily P&L

```text
MTM Change = Value(t) - Value(t-1)
Total P&L = MTM Change + Net Cashflow
Loss = -Total P&L
```

Cashflows paid between consecutive available valuation dates are assigned to the later valuation
row. This retains payments that occur after a weekend or market-data gap.
