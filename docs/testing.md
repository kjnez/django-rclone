# Testing

This project has two test layers:

- Unit/command tests: fast, no external database services required.
- Integration tests: real `rclone` + database CLI tools, with optional PostgreSQL/MySQL containers.

## Unit tests

Install base development dependencies:

```bash
uv sync
```

`uv sync` installs runtime dependencies plus the default `dev` group (pytest, lint/type tools, coverage, and docs tooling).

Run unit tests:

```bash
uv run pytest --cov --cov-branch
```

Integration tests are excluded by default via pytest config (`addopts = -m "not integration"`).

## Integration tests

Integration tests live in `tests/integration/` and use pytest markers:

- `integration`
- `requires_postgres`
- `requires_mysql`

Start containerized databases (optional but recommended):

```bash
docker compose up -d postgres mysql
```

Install integration-only Python dependencies:

```bash
uv sync --group integration
```

Run integration tests:

```bash
uv run pytest tests/integration -m integration -q
```

Stop containers when finished:

```bash
docker compose down
```

### What integration tests cover

- Database backup/restore round-trip for SQLite, PostgreSQL, and MySQL.
- Database cleanup retention behavior (`dbbackup --clean`).
- Backup listing output (`listbackups`).
- Media backup/restore round-trip.
- Signal emission during DB/media backup and restore commands.

### Requirements checked by integration tests

Tests are skipped automatically when required tools are missing.

- Always needed for DB/media integration tests: `rclone`
- SQLite integration tests: `sqlite3`
- PostgreSQL integration tests: `pg_dump`, `pg_isready`, and a Python PostgreSQL driver (`psycopg` or `psycopg2`)
- MySQL integration tests: `mysqldump`, `mysqladmin`, and `mysqlclient` (`MySQLdb`, 2.2.1+)

### Environment variables

You can override integration connection settings:

- PostgreSQL: `TEST_PG_HOST`, `TEST_PG_PORT`, `TEST_PG_USER`, `TEST_PG_PASSWORD`, `TEST_PG_NAME`
- MySQL: `TEST_MYSQL_HOST`, `TEST_MYSQL_PORT`, `TEST_MYSQL_USER`, `TEST_MYSQL_PASSWORD`, `TEST_MYSQL_NAME`
- SQLite file path: `TEST_SQLITE_NAME`

These default to the values in `docker-compose.yml` (for PostgreSQL/MySQL) and `/tmp/django_rclone_integration.sqlite3` (SQLite).

Note: when `TEST_MYSQL_HOST` is `localhost`, integration fixtures normalize it to `127.0.0.1` so `mysqlclient` uses TCP instead of a Unix socket.
