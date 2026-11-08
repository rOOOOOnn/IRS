# Contract Facts and Assumptions

The supplied case description verifies the USD 10,000,000 notional, 3.356% fixed rate,
pay-fixed/receive-floating direction, and compounded SOFR reference.

The following remain research assumptions because the disclosure did not provide them:

- effective date: 2023-05-01;
- maturity date: 2028-05-01;
- annual fixed payments;
- Actual/360 fixed and floating day counts;
- United States Government Bond calendar;
- Modified Following adjustment;
- two-business-day payment lag;
- zero observation lookback, no observation shift, and no lockout;
- ex-cashflow daily valuation basis;
- single-curve SOFR projection and discounting.

Every item, status, and source note is stored in `config/contract.yaml`. Changing a convention does
not require changing pricing code.
