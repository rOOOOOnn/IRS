# Assumptions and Open Issues

## Verified Case Facts

The supplied case material identifies a USD 10 million pay-fixed / receive-floating SOFR IRS with a 3.356% fixed rate. These facts should be rechecked against the original disclosure before the pricing phase.

## Research Assumptions

- Start date: 2023-05-01.
- Maturity: May 2028.
- Cash-flow conventions are not yet verified.

## Data Definition Issues

- `SOFRRATE` is an overnight fixing.
- `SOFRINDX` is a cumulative index, not a conventional interest rate.
- `USOSFR*` files are assumed to be OIS par-rate quotes by tenor, subject to workbook metadata confirmation.
- OIS par rates must not be relabelled as zero rates.
- USOSFR observations before 2018-04-02 are marked `PRE_SOFR_UNVERIFIED` and excluded from the main sample unless their Bloomberg historical definition is independently confirmed.
- Units must be verified from metadata and value magnitude before decimal conversion.

## Repository Security Issue

The project owner has chosen to keep source and processed market data in the shared repository for team reproducibility. The team remains responsible for confirming that this sharing method complies with the university's and data provider's applicable terms.
