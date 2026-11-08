# SOFR OIS Curve Methodology

## Market Instruments

Each valuation date is calibrated independently from the available Bloomberg USD SOFR OIS par
quotes. The required pricing nodes are 1M, 3M, 6M, 1Y, 2Y, 3Y, 4Y, and 5Y. The 7Y and 10Y
quotes are included when available but are not required for the five-year contract.

OIS par rates are passed to QuantLib `OISRateHelper` instruments; they are never treated as zero
rates. The helpers use a SOFR overnight index and the explicit assumptions in `config/curve.yaml`.

## Research Conventions

- Curve reference day count: Actual/365 Fixed.
- OIS fixed day count: Actual/360.
- Fixed frequency: annual.
- Calendar: United States Government Bond.
- Settlement days: two.
- Payment lag: two business days.
- Business-day convention: Modified Following.
- Averaging: compounded overnight SOFR.

These settings are research assumptions because the Bloomberg exports do not contain full
instrument convention metadata. They are centralized in configuration and are not presented as
SEC-disclosed contract facts.

## Interpolation and Bootstrap

Four separate QuantLib piecewise curves are bootstrapped from the same helpers:

1. `PiecewiseLinearZero`: linear interpolation on continuous zero rates.
2. `PiecewiseLogLinearDiscount`: log-linear interpolation on discount factors.
3. `PiecewiseNaturalCubicZero`: natural cubic interpolation on continuous zero rates.
4. `PiecewiseConvexMonotoneForward`: Hagan-West convex-monotone forward interpolation.

The convex-monotone implementation disables QuantLib's optional force-positive-forward constraint,
because the historical sample contains legitimate slightly negative rates. It uses a wider iterative
bootstrap search and higher evaluation limit. Every method is therefore calibrated independently;
the project does not bootstrap once and then cosmetically re-interpolate the resulting nodes.

## Query Interface

`OISCurve` exposes:

```python
curve.discount_factor(maturity_date)
curve.zero_rate(maturity_date)
curve.forward_rate(start_date, end_date)
```

Discount factors must be positive. Negative rates and discount factors greater than one are allowed.
Queries beyond the calibrated maximum date raise an error unless a validation experiment explicitly
enables endpoint extrapolation.

## Daily Database

The selected method is rebuilt independently on all 2,182 valid dates from 2018-04-02 through
2026-10-29. Test-set curves are built for valuation and backtesting but never feed method selection.

Primary references: [QuantLib term structures](https://quantlib-python-docs.readthedocs.io/en/latest/termstructures.html)
and [QuantLib rate helpers](https://quantlib-python-docs.readthedocs.io/en/latest/thelpers.html).
