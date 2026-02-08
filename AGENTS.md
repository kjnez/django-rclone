# Repository Guidelines

## Project Structure & Module Organization
Core package code lives in `src/django_rclone/`. Database connector implementations are in `src/django_rclone/db/`, and Django management commands are in `src/django_rclone/management/commands/` (`dbbackup`, `dbrestore`, `mediabackup`, `mediarestore`, `listbackups`).

Tests live in `tests/` and follow module-focused files like `test_rclone.py` and `test_commands.py`. Documentation source is in `docs/` with MkDocs config in `mkdocs.yml`. The `django-dbbackup/` directory is reference material only and is excluded from lint/type checks.

## Build, Test, and Development Commands
Use `uv` for all local workflows:

- `uv sync`: install project and dev dependencies.
- `uv run ruff check .`: run lint checks.
- `uv run ruff format --check .`: verify formatting.
- `uv run ty check`: run static type checks.
- `uv run pytest --cov --cov-branch`: run tests with coverage gating.

Run these before opening a PR; CI enforces the same checks.

## Coding Style & Naming Conventions
Target Python 3.12+ and keep code Ruff-clean. Formatting uses Ruff with double quotes and a 120-character line length.

Follow existing naming patterns:
- Modules/files: `snake_case.py`
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

Keep command and connector behavior explicit, and prefer small, focused functions over large procedural blocks.

## Testing Guidelines
Testing uses `pytest` + `pytest-django` with coverage via `pytest-cov`. Coverage is required at 100% (`fail_under = 100`), so every new branch/path needs tests.

Name tests as `test_*.py`, with test functions named `test_<behavior>()`. Add or update tests in the nearest matching file (for example, command logic in `tests/test_commands.py`).

## Commit & Pull Request Guidelines
Recent history uses short, imperative commit subjects (for example, `Fix subprocess deadlock in backup/restore commands`, `Add docs for cloudflare r2`). Follow that style and keep each commit scoped to one change.

PRs should include:
- A clear summary of what changed and why.
- Linked issue(s) when applicable.
- Updated tests/docs for behavior changes.
- Passing CI (lint, type check, tests, and coverage).
