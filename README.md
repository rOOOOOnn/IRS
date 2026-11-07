# RMSC5003 Interest Rate Swap Pricing and Risk Modelling

This repository supports the CUHK RMSC5003 group project on USD SOFR interest rate swaps. Phase 1 establishes a reproducible project structure, inspects and standardizes exported market data, defines chronological research periods, and documents the interfaces between the three team members.

> **Phase 1 boundary:** this version does not implement yield-curve bootstrapping, interpolation, calibration, IRS pricing, risk models, the decision-tree ensemble, or backtesting. Those modules contain interface documentation only.

## Case Study

The project studies a USD interest rate swap held by the John Hancock Financial Opportunities Fund.

### Verified facts from the supplied case material

- Notional: USD 10,000,000
- Fixed rate: 3.356%
- Position: pay fixed / receive floating
- Floating reference: compounded SOFR
- Currency: USD

### Research assumptions requiring confirmation

- Assumed start date: 2023-05-01
- Assumed maturity: May 2028
- Payment frequency, day-count conventions, calendars, reset rules, and other cash-flow conventions remain to be verified.

See [assumptions and issues](docs/assumptions_and_issues.md) before using the case terms in a model.

## Research Flow

```text
Bloomberg exports
  -> standardized market data
  -> daily zero curves (Phase 2)
  -> IRS daily MTM and P&L (Phase 2)
  -> HS / EWMA / PCA-MC risk forecasts
  -> dynamic ensemble forecasts
  -> VaR and ES backtesting
```

OIS par swap rates are inputs to a future curve engine. They are not zero rates and must not be passed to the final risk model as if they were zero rates.

## Team Responsibilities

| Member | Primary responsibility | Main future outputs | Working area |
|---|---|---|---|
| 陈美婷 | Historical Simulation, EWMA, PCA-based Monte Carlo, VaR and ES | `risk_model_outputs.csv` | `src/irs_project/risk/` |
| Faye | VaR/ES backtesting, Kupiec and Christoffersen tests, model comparison | `backtest_results.csv` | `src/irs_project/backtesting/` |
| Ron | Data, curve construction, IRS pricing, MTM/P&L, ensemble | `zero_curve_panel.csv`, `discount_factor_panel.csv`, `irs_mtm_pnl.csv`, `ensemble_outputs.csv` | `src/irs_project/data/`, `curves/`, `pricing/`, `ensemble/` |

Full ownership and handoff rules are in [team responsibilities](docs/team_responsibilities.md) and [data interfaces](docs/data_interfaces.md).

## Repository Structure

```text
config/                    Shared dates and project assumptions
data/raw/                  Shared source exports and their archive
data/interim/              Shared intermediate data when created
data/processed/            Reproducible standardized market data
data/sample/               Small synthetic test data safe for Git
docs/                      Scope, interfaces, definitions, setup, and workflow
outputs/                   Local figures, tables, and reports
src/irs_project/data/      Phase 1 inspection and preprocessing pipeline
src/irs_project/*/         Later-phase module boundaries and READMEs
tests/                     Unit tests using synthetic data
```

## Research Periods

| Dataset | Preset period | Purpose |
|---|---|---|
| Training | 2018-04-02 to 2021-12-31 | Estimation and parameter fitting |
| Validation | 2022-01-03 to 2023-04-28 | Model and hyperparameter selection |
| Inception / transition | 2023-05-01 to 2023-05-30 | Initial valuation and transition analysis |
| Test / backtesting | 2023-05-31 to latest valid date | Final out-of-sample evaluation |

The pipeline reports actual observations within these preset boundaries and never silently changes them. Curve construction and pricing will eventually run across the entire valid interval, including test dates. See [data split](docs/data_split.md).

## First-Time Setup

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
uv python install 3.11
uv sync --locked
uv run python --version
uv run pytest
```

The production workflow uses ordinary Python modules and command-line entry points. JupyterLab remains an optional environment tool for one-off exploration or presentation work; no project pipeline depends on a notebook. Detailed Windows and macOS instructions are in [environment setup](docs/environment_setup.md).

## Data Preprocessing

Source Excel exports are organized under `data/raw/bloomberg/` and are shared in this repository so every group member can reproduce the same pipeline.

```bash
uv run python -m irs_project.data.inspect
uv run python -m irs_project.data.preprocess
uv run python -m irs_project.data.validate
```

The pipeline creates shared outputs including `ois_quotes_long.csv`, `ois_par_rates_wide.csv`, `sofr_fixings.csv`, `sofr_index.csv`, `data_coverage.csv`, `data_manifest.csv`, `dataset_split_summary.csv`, and `outputs/reports/data_quality_report.md`.

It preserves raw values, keeps SOFR Index separate from rates, flags USOSFR observations before 2018-04-02 as `PRE_SOFR_UNVERIFIED`, and does not fill or delete missing values or outliers automatically.

## GitHub for Beginners

New GitHub users should follow [GitHub workflow for group members](docs/github_workflow.md). It explains cloning, creating a personal branch, committing, pushing, and opening a pull request on both Windows and macOS.

During Phase 1, the project setup is committed to `main`. Once parallel development starts, each member must work on a separate feature branch and merge through a pull request.

## Data and Credential Policy

The project owner has chosen to share the source exports and reproducible processed data in this repository so all group members have the same inputs. Each team member must still follow the university's and data provider's applicable terms. Passwords, API keys, tokens, private keys, `.env` files, and local virtual environments must never be committed.

## Next Phase

After the Phase 1 data definitions and coverage are approved, Ron will implement the curve and pricing engines. Risk and backtesting modules should consume only the documented interfaces and must preserve the no-look-ahead rules.
