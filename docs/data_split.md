# Chronological Dataset Split

The split dates are controlled by `config/project.yaml`. Random splitting is prohibited.

| Split | Preset period | Allowed use |
|---|---|---|
| Training | 2018-04-02 to 2021-12-31 | Parameter estimation, covariance, PCA, volatility, historical distributions |
| Validation | 2022-01-03 to 2023-04-28 | Hyperparameter and model selection, ensemble design |
| Inception / transition | 2023-05-01 to 2023-05-30 | Contract inception and initial valuation analysis |
| Test / backtesting | 2023-05-31 to latest valid date | Final out-of-sample evaluation only |

The pipeline reports actual counts and coverage within these fixed boundaries. It does not shift a date silently when the source lacks an observation.

## No-Look-Ahead Rules

1. Forecasts may use information available only through the previous day or the declared forecast timestamp.
2. Hyperparameters and ensemble rules must be fixed before final testing.
3. Rolling or expanding estimates may update only from observations available at that date.
4. Historical Simulation and PCA use the same information cutoff.
5. If validation data are insufficient for a decision tree, report the limitation instead of using test data.

## Curve and Pricing Coverage

The split is for risk modelling, selection, and backtesting. It does not restrict future curve construction or IRS pricing. Those engines should eventually run on every valid research date, including test dates, using only information available on each date.
