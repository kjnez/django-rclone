# django-rclone

[![CI](https://github.com/kjnez/django-rclone/actions/workflows/ci.yml/badge.svg)](https://github.com/kjnez/django-rclone/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-rclone)](https://pypi.org/project/django-rclone/)
[![Documentation](https://readthedocs.org/projects/django-rclone/badge/?version=latest)](https://django-rclone.readthedocs.io/)
[![codecov](https://codecov.io/gh/kjnez/django-rclone/graph/badge.svg)](https://codecov.io/gh/kjnez/django-rclone)
[![Python versions](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](https://pypi.org/project/django-rclone/)
[![Django versions](https://img.shields.io/badge/django-5.2%20%7C%206.0-blue)](https://www.djangoproject.com/)

Django database and media backup management commands, powered by [rclone](https://rclone.org/).

django-rclone bridges Django's database layer with rclone's file transfer layer. You get native database dumps piped directly to any of rclone's 70+ supported cloud storage backends -- no temp files, no intermediate archives, no Python reimplementations of what rclone already does.

**[Full documentation](https://django-rclone.readthedocs.io/)**

## Why rclone instead of Django Storages?

[django-dbbackup](https://github.com/Archmonger/django-dbbackup) is a mature and well-regarded backup solution. It wraps Django Storages for upload, implements GPG encryption in Python, handles gzip compression, and parses filenames with regex to manage backups.

django-rclone takes a different approach: **delegate everything that isn't Django-specific to rclone**.

| Concern | django-dbbackup | django-rclone |
|---|---|---|
| **Storage backends** | Django Storages (S3, GCS, etc.) | rclone (70+ backends natively) |
| **Encryption** | GPG subprocess wrapper in Python | rclone `crypt` remote |
| **Compression** | gzip in Python | rclone `compress` remote or `--compress` flag |
| **Media backup** | Tar archive, then upload | `rclone sync` (incremental, no archiving) |
| **Backup listing** | Filename regex parsing | `rclone lsjson` (structured JSON) |
| **Temp files** | `SpooledTemporaryFile` | None -- pipes directly via `rclone rcat` |
| **DB passwords** | Passed via CLI args (visible in `ps`) | Env vars for PostgreSQL/MySQL (`PGPASSWORD`, `MYSQL_PWD`) |

The result is significantly less code doing significantly less work. Storage abstraction, encryption, compression, and incremental sync are all rclone's problem -- django-rclone only owns what Django must own: database connectors, management commands, and signals.

## Requirements

- Python 3.12+
- Django 5.2+
- [rclone](https://rclone.org/install/) installed and configured

## Installation

```bash
pip install django-rclone
```

Add to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "django_rclone",
]
```

Configure your rclone remote (see [rclone docs](https://rclone.org/docs/)):

```bash
rclone config
```

Then point django-rclone at it:

```python
DJANGO_RCLONE = {
    "REMOTE": "myremote:backups",
}
```

## Usage

### Database backup and restore

```bash
# Backup the default database
python manage.py dbbackup

# Backup a specific database
python manage.py dbbackup --database analytics

# Backup and clean old backups beyond retention count
python manage.py dbbackup --clean

# Restore from the latest backup
python manage.py dbrestore

# Restore a specific backup
python manage.py dbrestore --input-path default-2024-01-15-120000.dump

# Non-interactive restore (for automation)
python manage.py dbrestore --noinput --input-path default-2024-01-15-120000.dump
```

### Media backup and restore

```bash
# Sync MEDIA_ROOT to remote (incremental -- only changed files transfer)
python manage.py mediabackup

# Sync remote back to MEDIA_ROOT
python manage.py mediarestore
```

### List backups

```bash
# List all database backups
python manage.py listbackups

# Filter by database
python manage.py listbackups --database default

# List media files on remote
python manage.py listbackups --media
```

## Configuration

All settings live under the `DJANGO_RCLONE` dict in your Django settings:

```python
DJANGO_RCLONE = {
    # Required -- rclone remote and base path
    "REMOTE": "myremote:backups",

    # Optional -- rclone binary and config
    "RCLONE_BINARY": "rclone",             # Path to rclone binary
    "RCLONE_CONFIG": None,                 # Path to rclone.conf (None uses default)
    "RCLONE_FLAGS": [],                    # Extra flags for every rclone call

    # Database backup settings
    "DB_BACKUP_DIR": "db",                 # Subdirectory for DB backups
    "DB_FILENAME_TEMPLATE": "{database}-{datetime}.{ext}",  # Must start with {database}
    "DB_DATE_FORMAT": "%Y-%m-%d-%H%M%S",
    "DB_CLEANUP_KEEP": 10,                 # Keep N most recent backups per database

    # Media backup settings
    "MEDIA_BACKUP_DIR": "media",           # Subdirectory for media backups

    # Database connector overrides
    "CONNECTORS": {},                      # Per-database connector class overrides
    "CONNECTOR_MAPPING": {},               # Engine-to-connector class overrides
}
```

### Encryption and compression

django-rclone does not implement encryption or compression. Instead, configure these at the rclone level where they belong:

**Encryption** -- use a [crypt remote](https://rclone.org/crypt/):

```bash
rclone config create myremote-crypt crypt remote=myremote:backups password=your-password
```

Then set `"REMOTE": "myremote-crypt:"` in your Django settings.

**Compression** -- use a [compress remote](https://rclone.org/compress/):

```bash
rclone config create myremote-compressed compress remote=myremote:backups
```

Or pass `--compress-level` via `RCLONE_FLAGS`.

See [Storage Providers](https://django-rclone.readthedocs.io/en/latest/providers/) for provider-specific configuration notes (Cloudflare R2, etc.).

## Supported databases

| Database | Connector | Dump tool | Format |
|---|---|---|---|
| PostgreSQL | `PgDumpConnector` | `pg_dump` / `pg_restore` | Custom (binary) |
| PostGIS | `PgDumpGisConnector` | `pg_dump` / `pg_restore` | Custom (binary) |
| MySQL / MariaDB | `MysqlDumpConnector` | `mysqldump` / `mysql` | SQL text |
| SQLite | `SqliteConnector` | `sqlite3 .dump` | SQL text |
| MongoDB | `MongoDumpConnector` | `mongodump` / `mongorestore` | Archive (binary) |

GIS backends (`postgis`, `spatialite`, `gis/mysql`) and `django-prometheus` wrappers are also mapped automatically. See [connectors documentation](docs/connectors.md) for the full engine mapping table.

## Signals

django-rclone sends Django signals before and after each operation:

```python
from django_rclone.signals import pre_db_backup, post_db_backup

@receiver(post_db_backup)
def notify_on_backup(sender, database, path, **kwargs):
    logger.info("Database %s backed up to %s", database, path)
```

Available signals: `pre_db_backup`, `post_db_backup`, `pre_db_restore`, `post_db_restore`, `pre_media_backup`, `post_media_backup`, `pre_media_restore`, `post_media_restore`.

## Architecture

```
Management Commands (dbbackup, dbrestore, mediabackup, mediarestore, listbackups)
        |                           |
   DB Connectors              rclone.py
   (pg, mysql, sqlite,    (subprocess wrapper)
    mongodb)
        |                           |
   Database binary              rclone binary
                          (70+ storage backends)
```

Database dumps stream directly from the dump process into `rclone rcat` via Unix pipes. No intermediate files are written. Restores work in reverse: `rclone cat` streams into the database restore process. Subprocess finalization is centralized and deadlock-safe (pipe draining + stderr collection).

Media backups use `rclone sync`, which is incremental by default -- only changed files are transferred.

## Development

Contributions are welcome. This project enforces **100% test coverage** -- all new code must be fully covered by tests. The CI pipeline will fail if coverage drops below 100%.

CI also includes subprocess guardrail tests to prevent `wait()`-based pipe deadlocks and to keep raw `Popen(...)` usage confined to the wrapper modules.

```bash
uv sync                                  # Install dependencies
uv run pytest --cov --cov-branch          # Run tests with coverage
uv run ruff check .                      # Lint
uv run ruff format --check .             # Check formatting
uv run ty check                          # Type check
```

## License

MIT
