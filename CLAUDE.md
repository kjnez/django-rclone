# django-rclone

Django package that wraps rclone for database and media file backups. Intended as a replacement for `django-dbbackup`.

The `django-dbbackup/` directory is included for reference only — it is not part of this project.

## Document lookup
Use `context7` to check documentation of packages.

## Development

```bash
uv sync                      # Install dependencies
uv run ruff check .          # Lint
uv run ruff format --check . # Check formatting
uv run ty check              # Type check
uv run pytest                # Run tests
```

## CI

GitHub Actions runs lint, type check, and tests on every push/PR. See `.github/workflows/ci.yml`.
