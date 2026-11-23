# IRS Pricing Methodology

## Position and Valuation Basis

The research contract is pay fixed / receive compounded SOFR, so:

```text
Market Value = PV Floating - PV Fixed
```

The engine uses an ex-cashflow value. A settled coupon is removed from market value and included once
in `Net_Cashflow`, preventing payment-date double counting.

## Fixed Leg

The fixed leg uses the disclosed semiannual schedule, Actual/360 accrual fractions, payment lag, and
business-day adjustment:

```text
PV Fixed = Notional × Fixed Rate × sum(Accrual Fraction × Discount Factor)
```

## Compounded SOFR Leg

The floating leg uses its own quarterly schedule, as disclosed in the SEC filing.

- Fully realized accrual periods use the ratio of SOFR Index values.
- A partially realized period combines the realized SOFR Index factor through the valuation date
  with the current curve's forecast factor for the remaining period.
- Fully future periods use the single-curve discount-factor ratio.
- The engine never reads a realized SOFR observation after the valuation date.

The project deliberately uses one SOFR OIS curve for both projection and discounting. Observation
conventions are recorded in `config/contract.yaml`. Pricing supports zero lookback, no shift,
and zero lockout. Contract validation rejects the unsupported alternatives.

### Dates without an exact SOFR Index

If an OIS valuation date falls inside an active accrual period and has no published Index,
daily pricing splits the coupon factor into three pieces. The published Index ratio compounds
through the last observation. The curve from that observation date projects the elapsed gap
using the reciprocal discount factor to the valuation date. The valuation-date curve projects
the remaining coupon. If the prior curve inputs are unavailable, valuation fails explicitly.
The valuation-only projection leaves published SOFR history and settled cashflows intact.
Settled periods require exact published Index boundaries.

The valuation panel records the published anchor in `SOFR_Index_As_Of` and the projected
multiplier in `Projected_SOFR_Carry_Factor`. When the multiplier is present,
`Accrued_Floating` includes estimated carry. Risk forecast cutoffs still require an exact Index.

## Daily P&L

```text
MTM Change = Value(t) - Value(t-1)
Total P&L = MTM Change + Net Cashflow
Loss = -Total P&L
```

Cashflows paid between consecutive available valuation dates are assigned to the later valuation
row. This retains payments that occur after a weekend or market-data gap.
