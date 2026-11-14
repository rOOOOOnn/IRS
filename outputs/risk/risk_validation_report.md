# Risk integration validation

- Base repository commit: `62cdec9a1e2e4678bb9bcd2cfb6f86d4c0a350c7`.
- Environment: Python 3.11.5 and project `uv.lock`; `uv sync --locked --all-groups` succeeded.
- Full project Ruff check: passed. Changed Python file format check: passed.
- Full project tests: **33 passed**, including original curve/data/pricing tests.
- Full OOS run: **2023-05-31 through 2026-10-29**.
- Candidate dates: **877**; all dates have 3 models x 2 confidence rows.
- Required output rows: **5262**, exact seven-column schema, no duplicate keys.
- Complete successful dates: **830**; numerical forecast rows: **4980**.
- Failed dates: **47**; empty forecast rows: **282**.
- Every finite prediction aligns to the next saved total-PnL interval: **PASS**.
- Maximum same-date zero-shock/scalar pricing error: **0 USD**.
- Maximum horizon batch/scalar zero-shock error: **0 USD**.
- Maximum reconstructed cutoff/main saved pricing error: **1.58e-06 USD**.
- All successful windows have exactly 500 valid changes and endpoint <= cutoff: **PASS**.
- Input and implementation hashes match the generated manifest: **PASS**.
- Future-data mutation tests, nonparallel batch/scalar checks, payment-date cashflow
  reconciliation, maturity settlement, missing Index and insufficient history tests: **PASS**.

## Failure counts (unique target dates)

- 30: ValueError: Nonbusiness forecast/cutoff date
- 16: ValueError: Realized PnL interval differs from forecast horizon
- 1: ValueError: Missing exact cutoff SOFR Index; refusing stale forward filling

All 47 failed target dates are retained with empty VaR/ES, not replaced by zero or removed.
The factor audit records excluded history; diagnostics retain all simultaneous data issues.
These are explicit data/calendar/P&L-alignment limitations, not claims of complete numerical coverage.

## Model assumption retained for the report

Unpublished future SOFR Index is deterministically projected from the information-cutoff curve.
This forecasts cashflow-adjusted total P&L without future observations but does not simulate an
additional overnight-fixing surprise. The original configurable contract conventions, selected
curve method, Index-ratio compounding engine and dirty/ex-cashflow PV convention are preserved.
