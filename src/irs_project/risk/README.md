# Rolling market-risk forecasts

Run from the project root after the curve and pricing pipelines:

```bash
uv sync --locked --all-groups
uv run python -m scripts.run_risk_models
```

This produces the complete test-period output at `outputs/risk/risk_model_outputs.csv`.
HS, EWMA and PCA_MC share 1M–5Y zero-rate changes, `config/contract.yaml`, the selected
curve factory, and the same cashflow-aware horizon repricer. No simplified swap or bootstrap
implementation is embedded in the risk models.

Parameters are fixed in `config/risk.yaml`: rolling 500 valid changes, 50,000 Monte Carlo
scenarios, decay 0.94, three PCA factors, and 95%/99% risk levels. These defaults are not
claimed to have been optimized on Validation; do not tune them on final Test performance.

See `docs/risk_methodology.md` for date semantics, SOFR projection, failure records and
consumer checks. All failures are retained as empty VaR/ES with a separate diagnostic reason.
The pipeline does not fill failed forecasts with zero or silently remove dates.

Smoke tests write to `outputs/risk_smoke/`, never over the complete production output:

```bash
uv run python -m scripts.run_risk_models --max-dates 3 --simulations 1000
uv run ruff check .
uv run pytest
```
