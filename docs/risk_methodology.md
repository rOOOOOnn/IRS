# Shared-engine rolling HS, EWMA and PCA Monte Carlo

## Run and dependencies

Use the current main project's curve/pricing implementation and its locked Python 3.11 environment:

```bash
uv sync --locked --all-groups
uv run python -m scripts.run_risk_models
uv run ruff check .
uv run pytest
```

The risk-only command consumes the existing processed/curve/pricing files; it does not rebuild
curves for all dates or overwrite the saved IRS P&L. It constructs each cutoff curve through
`curve_from_market_row`, using the frozen Validation-selected interpolation method. OIS quotes
are consumed only by that shared curve factory, never as risk-factor shocks.

## Files and interfaces

The required file is `outputs/risk/risk_model_outputs.csv`, with exactly:

```text
Date,Model,Confidence_Level,Forecast_Horizon,VaR,ES,Forecast_As_Of
```

Model values are `HS`, `EWMA`, `PCA_MC`. Rates and confidence levels are decimals; risk amounts
are USD positive loss magnitudes. Negative empirical quantiles are floored at zero at the output
boundary to honor the existing interface, not by altering scenario losses.

Additional audit files do NOT alter the seven-column handoff schema:

- `risk_forecast_diagnostics.csv`: one row per model/target, status, reason, information cutoff,
  calendar duration, window endpoints/count, scenario count, PCA variance and consistency errors.
- `risk_factor_audit.csv`: every source change row with validity or an explicit exclusion reason.
- `risk_pnl_alignment.csv`: one row per target with actual P&L interval start, realized Loss and
  `MATCHED`, `UNAVAILABLE` or `PNL_INTERVAL_MISMATCH`.
- `risk_run_manifest.json`: parameters, source/code hashes, coverage and model assumptions.

A failed model/date retains its two confidence rows with empty VaR/ES; neither zero-filling nor
scenario deletion is allowed. A mismatch between the saved P&L interval and forecast horizon is
also a failed forecast. Legitimate large finite historical changes are retained, not winsorized.
Nonbusiness dates, source gaps and level/change inconsistencies are explicitly audited.

## Date semantics

- `Date = u`: target/realization date, starting exactly at the configured Test boundary 2023-05-31.
- `Forecast_As_Of = t`: preceding observed market date, interpreted as end of day t.
- Information cutoff: end of t. All historical changes have endpoint <= t.
- `Forecast_Horizon = 1D`: the next observed market interval (t,u], not a square-root-scaled number
  of calendar days. Weekend/holiday calendar lengths are recorded separately in diagnostics.
- P&L match: join Date to `irs_mtm_pnl.Date` and require its previous valuation date to equal t.
  This prevents accidentally comparing a one-interval forecast with a P&L spanning missing dates.

Candidate target dates come from the union of source quote dates, from the Test start through
the configured Test end or the last valid zero-curve date. Missing-curve and nonbusiness candidate
dates remain visible as failure records. Historical shocks spanning a missing market observation
are excluded instead of being treated as one-day changes. Optional 7Y/10Y changes are not needed.

## Information isolation

Each model uses the same most recent 500 valid rows from `zero_rate_changes.csv`, with columns
`Delta_Zero_1M`, `3M`, `6M`, `1Y`, `2Y`, `3Y`, `4Y`, `5Y`. Values are reconciled against consecutive
rows of `zero_curve_panel.csv`; source rows that span missing quote observations are excluded.
The first differenced row is invalid by construction and is logged, not imputed.

The model reads the configured Training start; rolling windows may then include earlier Test
observations once they have actually become known. Window length, decay, factor count and curve
selection are fixed before Test evaluation. The latter is checked against selection provenance.
There is no random time split. Date/model-keyed random streams are reproducible when running
subsets. Mutating data strictly after a cutoff leaves its numerical forecasts unchanged.

SOFR histories passed to cutoff valuation are physically truncated at t. Index dated t is assumed
published/available by end of t, consistent with the main project's daily Index convention. This is
an EOD research convention, not an intraday availability claim. Missing exact cutoff Index or
required known accrual-boundary Index observations fail explicitly; stale boundary filling is
not used in this layer.

## Shared pricing and the holding-period P&L

The real contract, adjusted schedule, ACT/360 coupons, payment lag, remaining maturity, realized
SOFR Index compounding, and settled cashflows come from the existing pricing modules. A small
refactor extracts a common `discounted_leg_values` kernel from `price_irs`. Scalar main-engine
pricing and vectorized risk scenarios call that identical kernel and the existing fixed/floating
coupon functions. The former simplified annual bootstrap/pricer is not included.

The existing `ScenarioCurve` interpolation and discount-shock convention is reused. Its batch
counterpart is checked against scalar repricing for zero, parallel and nonparallel shocks. The
same-date zero shock must equal the main engine before any forecast is emitted. Cutoff valuations
are also reconciled against the saved `irs_mtm_pnl.csv` baseline to a USD 1e-5 tolerance.

A fixed-date market-value shock alone does not forecast the project's `Total_PnL`. Therefore the
adapter rolls the cutoff curve to u using forward discount ratios:

```text
D_roll(u,T) = D_t(T) / D_t(u)
D_scenario(u,T) = D_roll(u,T) * exp(-interpolated_zero_shock(T) * year_fraction(u,T))
scenario Total_PnL = V_scenario(u) - V(t) + settled_net_cashflow(t,u]
scenario Loss = -scenario Total_PnL
```

At u, matured/paid cashflows disappear from remaining PV; payments in (t,u] are added once.
The same-date zero-shock equality test differs from the horizon zero-shock value: the latter
can legitimately differ from V(t) because of carry, time passage and coupon settlement.

## Future SOFR is a forecast assumption, never observed future data

SOFR Index values between t and u are not known at t. They are projected from the cutoff curve:

```text
Projected_Index(d) = Known_Index(t) / D_t(d),  t < d <= u
```

The projection includes any intervening accrual/payment boundary. This is an explicitly modeled
future Index, stored only in the in-memory scenario history; it is not written into realized
source data. It is common to every scenario/model (deterministic overnight carry). No observed
Index/fixing dated after t is passed into forecasting. Consequently it does not model an extra
independent overnight-fixing surprise. That residual model risk must remain in the report.

The supplied project engine uses SOFR Index ratios rather than rebuilding realized compounding
from individual daily fixings. This integration preserves that engine behavior. Nonzero lookback,
observation shift or lockout is rejected because the shared engine does not implement those
alternatives; unsupported conventions are not silently approximated.

## Shock models

- HS: replay the 500 full zero-change vectors with equal probability, without demeaning.
- EWMA: zero expected daily change, covariance recursion `S=lambda*S+(1-lambda)*dx*dx.T`,
  chronological order, initialized with the first observation outer product; full-factor Gaussian MC.
- PCA_MC: sample covariance, descending eigenpairs, retain the configured three components,
  independent standard Gaussian factors mapped back into all eight zero tenors; zero expected change.
  Discarded factor risk and explained variance are reported. PCA does not imply Gaussian tails.

All three use exact shared-engine scenario revaluation rather than delta-only P&L. Empirical VaR
uses inverse-CDF quantiles; ES integrates the worst probability mass including fractional boundary
weight. Every simulated loss must be finite; a valuation failure rejects that model/date as a whole.

## Consumer example

Consumers should explicitly report missing forecasts instead of quietly dropping them:

```python
import pandas as pd

risk = pd.read_csv("outputs/risk/risk_model_outputs.csv", parse_dates=["Date", "Forecast_As_Of"])
status = pd.read_csv("outputs/risk/risk_forecast_diagnostics.csv", parse_dates=["Date"])
pnl = pd.read_csv("outputs/pricing/irs_mtm_pnl.csv", parse_dates=["Date"]).sort_values("Date")
pnl["PnL_Previous_Date"] = pnl["Date"].shift()

print(status["Status"].value_counts())
joined = risk.merge(pnl[["Date", "Loss", "PnL_Previous_Date"]], on="Date", how="left",
                    validate="many_to_one")
valid = joined["VaR"].notna() & joined["ES"].notna()
assert (joined.loc[valid, "Forecast_As_Of"] == joined.loc[valid, "PnL_Previous_Date"]).all()
```

Do not replace missing VaR/ES with zero in an ensemble. Compare models on a documented common
successful sample and report excluded targets separately. Backtesting/ensemble statistical tests
are separate modules; this change supplies their inputs rather than claiming test-period calibration.
