# Cross-Platform Environment Setup

## Why uv and Python 3.11

The project uses uv as the single environment and dependency manager. Python 3.11 is pinned so Windows and macOS run the same supported interpreter and exact versions recorded in `uv.lock`.

Do not create a Conda or Poetry environment for this project. Each member keeps a local `.venv`, which is never committed.

## Install Git and uv

### Windows

1. Install Git from <https://git-scm.com/download/win>.
2. Open PowerShell.
3. Install uv from <https://docs.astral.sh/uv/getting-started/installation/>.

### macOS

1. Open Terminal and run `xcode-select --install` if Git is unavailable.
2. Install uv from <https://docs.astral.sh/uv/getting-started/installation/>.

## First-Time Project Setup

From the cloned repository:

```bash
uv python install 3.11
uv sync --locked
uv run python --version
uv run pytest
```

Optional: launch JupyterLab for one-off exploration or presentation work:

```bash
uv run jupyter lab
```

The production preprocessing workflow uses ordinary Python modules rather than notebooks. In VS Code, select `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on macOS. If JupyterLab is used for optional exploration, select the kernel from the project environment.

## After Pulling Updates

```bash
git pull --ff-only origin main
uv sync --locked
```

## Adding a Dependency

```bash
uv add package-name
uv add --dev development-package
```

Commit both `pyproject.toml` and `uv.lock`. Never ask teammates to install an undeclared package manually.

## Common Problems

- **Wrong Python:** `uv run python --version` must show Python 3.11.x.
- **Stale environment:** run `uv sync --locked`.
- **Wrong notebook kernel:** select the interpreter under the repository's `.venv`.
- **Path errors:** run commands from the repository root; Python uses relative `pathlib` paths.
- **Excel add-in unavailable:** the pipeline reads exported files and does not require Bloomberg or Excel COM.
