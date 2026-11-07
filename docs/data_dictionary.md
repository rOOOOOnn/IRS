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

Other outputs are defined in `docs/data_interfaces.md`. `data_coverage.csv` stores coverage and quality statistics; `data_manifest.csv` stores raw path, SHA-256 hash, workbook metadata, and processing status.
