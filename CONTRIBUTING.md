# Contributing

## Branch Strategy

Phase 1 project setup is maintained on `main`. Once parallel development begins, each member creates a branch from an up-to-date `main`:

```bash
git switch main
git pull --ff-only origin main
git switch -c <name>/<short-task>
```

Examples: `meiting/ewma-risk`, `faye/var-backtesting`, `ron/curve-engine`.

Do not push directly to `main` during parallel development. Push the feature branch and open a pull request. See [the beginner GitHub guide](docs/github_workflow.md).

## File Naming

- Python modules: lowercase `snake_case.py`
- CSV outputs: lowercase `snake_case.csv`
- Data dates: ISO 8601 `YYYY-MM-DD`
- Avoid spaces and machine-specific paths.

## Python Conventions

- Use Python 3.11 and uv only.
- Use `pathlib.Path`, relative project paths, type hints, and UTF-8.
- Do not use Excel COM automation or hard-coded Windows paths.
- Run `uv run ruff check .` and `uv run pytest` before a pull request.

## Data Interface Rules

- Follow `docs/data_interfaces.md`.
- Preserve raw values and provenance.
- Do not silently change units, signs, dates, or column names.
- `Daily_PnL = V_t - V_(t-1)` and `Loss = -Daily_PnL`.
- OIS par rates are not zero rates.
- Test data must never be used for model or ensemble selection.
- Keep shared raw and processed data in their documented `data/` locations; never mix credentials or personal files into data commits.

## Commit Messages

Use an imperative, specific subject such as `Add Bloomberg workbook inspection` or `Fix duplicate-date validation`. Keep unrelated changes in separate commits.
