# Risk Integration Validation

The IRS uses semiannual fixed and quarterly floating payments. The rolling risk forecasts use
the same pricing engine, with scenario tenor dates adjusted using the curve export calendar
and business-day convention. The audited carry correction uses the prior published Index
and its date's curve on the affected valuation dates. Forecast cutoffs still require an exact
published Index.

- Full out-of-sample run: 2023-05-31 through 2026-10-29.
- Candidate dates: 877. Forecast rows: 5,262.
- Common successful dates: 830. Excluded dates: 47.
- Maximum same-date zero-shock error: USD 0.
- Maximum horizon batch/scalar zero-shock error: USD 0.
- Maximum cutoff versus saved pricing error: USD 5.82e-11.

The forecast dates, model statuses, rolling windows and exclusion reasons match the audit
baseline. The adjusted tenor grid changes scenario prices and the resulting VaR and ES levels.
The realized loss on 2026-04-03 remains in the common sample after correcting its valuation.
The next forecast is excluded because its cutoff has no exact Index. See the
[pricing audit](../FINANCIAL_AUDIT_REPORT.md) and [backtest report](../backtesting/model_comparison.md).
