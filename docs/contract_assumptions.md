# Contract Facts and Assumptions

The supplied case description verifies the USD 10,000,000 notional, 3.356% fixed rate,
pay-fixed/receive-floating direction, compounded SOFR reference, semiannual fixed payments,
and quarterly floating payments.

The following remain research assumptions because the disclosure did not provide them:

- effective date: 2023-05-01;
- maturity date: 2028-05-01;
- Actual/360 fixed and floating day counts;
- United States Government Bond calendar;
- Modified Following adjustment;
- two-business-day payment lag;
- zero observation lookback, no observation shift, and no lockout;
- ex-cashflow daily valuation basis;
- single-curve SOFR projection and discounting.

Every item, status, and source note is stored in `config/contract.yaml`. The compounded-SOFR
engine supports zero lookback, no observation shift, and zero lockout. Contract validation
rejects any other values for these three settings.
