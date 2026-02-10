# django-rclone

Django database and media backup management commands, powered by [rclone](https://rclone.org/).

django-rclone bridges Django's database layer with rclone's file transfer layer. You get native database dumps piped directly to any of rclone's 70+ supported cloud storage backends -- no temp files, no intermediate archives, no Python reimplementations of what rclone already does.

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

The result is significantly less code doing significantly less work. Storage abstraction, encryption, compression, and incremental sync are all rclone's problem -- django-rclone only owns what Django must own: database connectors, management commands, and signals.

## Requirements

- Python 3.13+
- Django 4.2+
- [rclone](https://rclone.org/install/) installed and configured

## Quick start

```bash
pip install django-rclone
```

```python
INSTALLED_APPS = [
    # ...
    "django_rclone",
]

DJANGO_RCLONE = {
    "REMOTE": "myremote:backups",
}
```

```bash
python manage.py dbbackup       # Backup database
python manage.py dbrestore      # Restore latest backup
python manage.py mediabackup    # Sync media files to remote
python manage.py mediarestore   # Sync media files from remote
python manage.py listbackups    # List all backups
```

See the [Getting Started](getting-started.md) guide for a full walkthrough.

## Supported databases

| Database | Connector | Dump tool | Format |
|---|---|---|---|
| PostgreSQL | `PgDumpConnector` | `pg_dump` / `pg_restore` | Custom (binary) |
| PostGIS | `PgDumpGisConnector` | `pg_dump` / `pg_restore` | Custom (binary) |
| MySQL / MariaDB | `MysqlDumpConnector` | `mysqldump` / `mysql` | SQL text |
| SQLite | `SqliteConnector` | `sqlite3 .dump` | SQL text |
| MongoDB | `MongoDumpConnector` | `mongodump` / `mongorestore` | Archive (binary) |

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

Database dumps stream directly from the dump process into `rclone rcat` via Unix pipes. No intermediate files are written. Restores work in reverse: `rclone cat` streams into the database restore process. The command layer finalizes subprocesses with centralized deadlock-safe pipe draining.

Media backups use `rclone sync`, which is incremental by default -- only changed files are transferred.
