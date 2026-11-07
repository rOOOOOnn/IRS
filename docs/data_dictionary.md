# Data Dictionary

## Raw Source Types

| Type | Meaning | Unit treatment |
|---|---|---|
| SOFR fixing | Daily overnight SOFR (`SOFRRATE`) | Preserve raw value; convert percent to decimal only when metadata and magnitude confirm percent units |
| SOFR Index | Cumulative compounded SOFR index (`SOFRINDX`) | Preserve as an index; never convert to a rate |
| OIS par quote | USD SOFR OIS market quote (`USOSFR*`) | Preserve raw quote; decimal field is a normalized par rate, not a zero rate |

## `ois_quotes_long.csv`

| Field | Definition |
|---|---|
| `Date` | Observation date in ISO 8601 |
| `Ticker` | Canonical Bloomberg ticker |
| `Tenor` | OIS tenor such as `1M` or `5Y` |
| `Rate_Raw` | Original numeric quote from the workbook |
| `Rate_Decimal` | Rate normalized to decimal after unit validation |
| `Source` | Source system and raw filename |
| `Field` | Bloomberg field when available |
| `Security_Description` | Workbook description when available |
| `Quality_Flag` | Semicolon-separated quality flags; `OK` when none apply |

## Curve-panel outputs

| File | Definition |
|---|---|
| `ois_par_rates_wide.csv` | Full merged ten-tenor market panel; 7Y/10Y and other unavailable quotes remain visibly empty |
| `ois_curve_inputs_5y.csv` | Official five-year curve input containing complete 1M-5Y nodes; 7Y and 10Y are not required |
| `incomplete_curve_dates.csv` | Dates excluded because at least one required 1M-5Y node is missing |
| `ois_curve_missingness_by_tenor.csv` | Missing-date count, rate, required/optional status, and treatment for every tenor |

Other outputs are defined in `docs/data_interfaces.md`. `data_coverage.csv` stores coverage and quality statistics; `data_manifest.csv` stores raw path, SHA-256 hash, workbook metadata, and processing status.
