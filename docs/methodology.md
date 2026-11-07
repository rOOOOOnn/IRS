# Phase 1 Methodology

1. Discover `.xlsx` files under the configured local raw-data directory.
2. Read workbook values and visible metadata using pandas/openpyxl.
3. Resolve the canonical series from workbook metadata first and the filename second.
4. Preserve raw values and record source filenames and hashes.
5. Normalize dates, sort ascending, and flag duplicate dates without silently aggregating.
6. Treat SOFR fixing, SOFR Index, and OIS par quotes as distinct data types.
7. Normalize confirmed percentage rates to decimals while retaining `Rate_Raw`.
8. Flag, but do not delete, pre-SOFR USOSFR records, duplicates, missing values, and robust jump outliers.
9. Produce long, wide, fixing, index, coverage, manifest, split-summary, and quality-report outputs.

No forward fill, backward fill, interpolation, winsorization, or outlier deletion occurs in Phase 1.
