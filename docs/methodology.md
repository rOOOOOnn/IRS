# Phase 1 Methodology

1. Discover `.xlsx` files under the configured local raw-data directory.
2. Read workbook values and visible metadata using pandas/openpyxl.
3. Resolve the canonical series from workbook metadata first and the filename second.
4. Preserve raw values and record source filenames and hashes.
5. Normalize dates, sort ascending, and flag duplicate dates without silently aggregating.
6. Treat SOFR fixing, SOFR Index, and OIS par quotes as distinct data types.
7. Normalize confirmed percentage rates to decimals while retaining `Rate_Raw`.
8. Flag, but do not alter, pre-SOFR USOSFR records, duplicates, missing values, and robust jump outliers in the traceable source-level outputs.
9. Preserve the full merged OIS panel and report every missing cell.
10. For the five-year curve input, require observed 1M, 3M, 6M, 1Y, 2Y, 3Y, 4Y, and 5Y nodes. A missing 7Y or 10Y quote alone does not exclude the date; a missing required node excludes the entire date from the curve input.
11. Produce long, wide, five-year curve-input, fixing, index, coverage, manifest, split-summary, and quality-report outputs.

No forward fill, backward fill, two-sided interpolation, winsorization, or outlier deletion occurs in Phase 1. Dropping an incomplete date applies only to `ois_curve_inputs_5y.csv`; the original quotes remain in the long and full wide files.
