# GitHub Workflow for First-Time Contributors

This guide assumes no previous Git or GitHub experience. Commands work in PowerShell on Windows and Terminal on macOS.

## 1. Get Access

1. Create a GitHub account and send the username to Ron.
2. Accept the collaborator invitation from GitHub email or notifications.
3. Open <https://github.com/rOOOOOnn/IRS> and confirm the repository is visible.

Never upload passwords, API keys, tokens, private keys, `.env` files, or `.venv`. Project market data belongs only in the documented `data/` directories.

## 2. Install the Tools

- Git: <https://git-scm.com/downloads>
- VS Code if desired: <https://code.visualstudio.com/>
- uv: <https://docs.astral.sh/uv/getting-started/installation/>

Check the tools:

```bash
git --version
uv --version
```

## 3. Configure Git Once

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

Use the name and email linked to your GitHub account.

## 4. Clone the Project

Choose a normal local folder, then run:

```bash
git clone https://github.com/rOOOOOnn/IRS.git
cd IRS
uv python install 3.11
uv sync --locked
uv run pytest
```

`clone` is done only once. Later updates use `pull`.

## 5. Create Your Own Branch

Before a new task:

```bash
git switch main
git pull --ff-only origin main
git switch -c your-name/short-task
```

Examples:

```bash
git switch -c meiting/ewma-risk
git switch -c faye/var-backtesting
git switch -c ron/curve-engine
```

Confirm the branch with `git branch --show-current`. Do not do normal feature work directly on `main`.

## 6. Work and Check Changes

```bash
git status
git diff
uv run ruff check .
uv run pytest
```

## 7. Commit Your Work

Stage only the intended files:

```bash
git add path/to/file.py docs/changed_file.md
git status
git commit -m "Add EWMA volatility estimator"
```

Avoid `git add .` until you understand every file listed by `git status`. Shared data updates must stay under `data/raw`, `data/interim`, or `data/processed` and should be described clearly in the commit message.

## 8. Push Your Branch

First push:

```bash
git push -u origin your-name/short-task
```

Later pushes on the same branch use `git push`. GitHub may open a browser for authentication; use your own account.

## 9. Open a Pull Request

1. Open the repository on GitHub.
2. Click **Compare & pull request**.
3. Set base to `main` and compare to your branch.
4. Explain the change, tests, and open issues.
5. Ask another member to review.
6. Merge only after review and passing checks.

## 10. Start the Next Task

```bash
git switch main
git pull --ff-only origin main
git branch -d your-name/short-task
git switch -c your-name/next-task
```

## 11. Update a Feature Branch from Main

Commit or stash current work first:

```bash
git switch main
git pull --ff-only origin main
git switch your-name/short-task
git merge main
```

If Git reports conflicts, do not guess. Resolve the marked sections with the relevant teammate, run tests, then:

```bash
git add path/to/resolved_file
git commit
git push
```

## 12. Safe Recovery Commands

- Check branch and changes: `git status`
- View recent commits: `git log --oneline -10`
- Unstage without deleting: `git restore --staged path/to/file`
- Save unfinished tracked changes: `git stash push -m "work in progress"`
- Restore them: `git stash pop`

Do not use `git reset --hard`, force-push, or rewrite shared history unless the team coordinates it.

## Daily Checklist

1. Confirm your branch.
2. Pull the latest `main` before a new task.
3. Keep commits small and specific.
4. Run tests before pushing.
5. Push only your branch.
6. Use a pull request to merge into `main`.
