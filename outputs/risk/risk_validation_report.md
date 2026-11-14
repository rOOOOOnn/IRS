# Risk integration validation

The IRS uses separate semiannual fixed and quarterly floating payment schedules.
Daily pricing and cashflow-adjusted P&L were regenerated before the risk run.

- Full out-of-sample run: 2023-05-31 through 2026-10-29.
- Candidate dates: 877. Forecast rows: 5,262.
- Complete successful dates: 830. Failed dates: 47.
- Maximum same-date zero-shock error: USD 0.
- Maximum horizon batch/scalar zero-shock error: USD 0.
- Maximum cutoff versus saved pricing error: USD 5.82e-11.
- Local test suite: 33 passed.

Failed dates consist of 30 nonbusiness forecast or cutoff dates, 16 P&L interval
mismatches and one missing exact cutoff SOFR Index. Forecasts on these dates are empty.
The model projects unpublished SOFR Index values from the cutoff curve.
