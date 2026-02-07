# Database Connectors

django-rclone uses a strategy pattern for database connectors. Each connector wraps a database's native dump/restore tools and exposes them as streaming subprocesses.

## Built-in connectors

### PostgreSQL -- `PgDumpConnector`

**Module:** `django_rclone.db.postgresql.PgDumpConnector`
**Engine:** `django.db.backends.postgresql`

Uses `pg_dump` with custom (binary) format for backups and `pg_restore` for restores.

- **Dump:** `pg_dump --format=custom [-h HOST] [-p PORT] [-U USER] DBNAME`
- **Restore:** `pg_restore --no-owner --no-acl -d DBNAME [-h HOST] [-p PORT] [-U USER]`
- **Extension:** `.dump`

**Security:** Passwords are passed via the `PGPASSWORD` environment variable, never as command-line arguments. This means the password is not visible in process listings (`ps aux`), unlike django-dbbackup which passes credentials via CLI args.

**Requirements:** `pg_dump` and `pg_restore` must be installed and on the system `PATH`. These are included in the `postgresql-client` package on Debian/Ubuntu.

### PostGIS -- `PgDumpGisConnector`

**Module:** `django_rclone.db.postgresql.PgDumpGisConnector`
**Engine:** `django.contrib.gis.db.backends.postgis`

Extends `PgDumpConnector` with PostGIS support. Before restoring, it runs `CREATE EXTENSION IF NOT EXISTS postgis;` to ensure the extension is available.

- **Dump/Restore:** Same as `PgDumpConnector`
- **Extension:** `.dump`

**Configuration:** Requires the `ADMIN_USER` key in your database settings. This user must have sufficient privileges to create extensions:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "geodb",
        "USER": "app_user",
        "PASSWORD": "...",
        "HOST": "localhost",
        "ADMIN_USER": "postgres",  # used for CREATE EXTENSION
    }
}
```

If `ADMIN_USER` is not set, the PostGIS enablement step is skipped and the connector behaves identically to `PgDumpConnector`.

**Requirements:** Same as `PgDumpConnector`, plus `psql` for the extension creation command.

### MySQL / MariaDB -- `MysqlDumpConnector`

**Module:** `django_rclone.db.mysql.MysqlDumpConnector`
**Engine:** `django.db.backends.mysql`

Uses `mysqldump` for backups and `mysql` for restores.

- **Dump:** `mysqldump --quick [--host HOST] [--port PORT] [--user USER] DBNAME`
- **Restore:** `mysql [--host HOST] [--port PORT] [--user USER] DBNAME`
- **Extension:** `.sql`

**Security:** Passwords are passed via the `MYSQL_PWD` environment variable, never as command-line arguments. This is a security improvement over django-dbbackup, which passes MySQL passwords directly on the command line.

**Requirements:** `mysqldump` and `mysql` must be installed and on the system `PATH`. These are included in the `mysql-client` or `mariadb-client` packages.

### SQLite -- `SqliteConnector`

**Module:** `django_rclone.db.sqlite.SqliteConnector`
**Engine:** `django.db.backends.sqlite3`

Uses the `sqlite3` command-line tool's `.dump` command for backups and pipes SQL statements back for restores.

- **Dump:** `sqlite3 DBNAME .dump`
- **Restore:** `sqlite3 DBNAME` (reads SQL from stdin)
- **Extension:** `.sqlite3`

**Requirements:** The `sqlite3` command-line tool must be installed. This is available by default on most systems.

### MongoDB -- `MongoDumpConnector`

**Module:** `django_rclone.db.mongodb.MongoDumpConnector`
**Engine:** `djongo`, `django_mongodb_engine`

Uses `mongodump` with `--archive` for streaming backups to stdout and `mongorestore` with `--archive` for streaming restores from stdin.

- **Dump:** `mongodump --db DBNAME --host HOST:PORT [--username USER] [--password PASS] [--authenticationDatabase SOURCE] --archive`
- **Restore:** `mongorestore --host HOST:PORT [--username USER] [--password PASS] [--authenticationDatabase SOURCE] --drop --archive`
- **Extension:** `.archive`

**Configuration:** MongoDB auth source can be set via the `AUTH_SOURCE` key in your database settings:

```python
DATABASES = {
    "default": {
        "ENGINE": "djongo",
        "NAME": "mydb",
        "HOST": "localhost",
        "PORT": "27017",
        "USER": "admin",
        "PASSWORD": "...",
        "AUTH_SOURCE": "admin",  # authentication database
    }
}
```

**Requirements:** `mongodump` and `mongorestore` must be installed and on the system `PATH`. These are included in the `mongodb-database-tools` package.

**Security note:** MongoDB tools currently require credentials via command arguments in this connector. If process-listing exposure is a concern, prefer host-level controls and short-lived credentials.

## Engine mapping

The following database engines are mapped to connectors by default:

| Engine | Connector |
|---|---|
| `django.db.backends.postgresql` | `PgDumpConnector` |
| `django.db.backends.sqlite3` | `SqliteConnector` |
| `django.db.backends.mysql` | `MysqlDumpConnector` |
| `django.contrib.gis.db.backends.postgis` | `PgDumpGisConnector` |
| `django.contrib.gis.db.backends.spatialite` | `SqliteConnector` |
| `django.contrib.gis.db.backends.mysql` | `MysqlDumpConnector` |
| `djongo` | `MongoDumpConnector` |
| `django_mongodb_engine` | `MongoDumpConnector` |
| `django_prometheus.db.backends.postgresql` | `PgDumpConnector` |
| `django_prometheus.db.backends.sqlite3` | `SqliteConnector` |
| `django_prometheus.db.backends.mysql` | `MysqlDumpConnector` |
| `django_prometheus.db.backends.postgis` | `PgDumpGisConnector` |

## Connector resolution order

When django-rclone needs a connector for a database, it checks in this order:

1. **`CONNECTORS` setting** -- per-database overrides by alias name
2. **`CONNECTOR_MAPPING` setting** -- engine-to-connector overrides, merged with defaults
3. **Built-in mapping** -- the table above

If no connector is found, a `ConnectorNotFound` exception is raised.

## Writing a custom connector

To support a new database or customize behavior, subclass `BaseConnector`:

```python
import os
import subprocess
from django_rclone.db.base import BaseConnector


class OracleConnector(BaseConnector):
    @property
    def extension(self) -> str:
        return "dmp"

    def dump(self) -> subprocess.Popen[bytes]:
        cmd = ["expdp", f"{self.user}/{self.password}@{self.host}:{self.port}/{self.name}"]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def restore(self, stdin=None) -> subprocess.Popen[bytes]:
        cmd = ["impdp", f"{self.user}/{self.password}@{self.host}:{self.port}/{self.name}"]
        return subprocess.Popen(cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
```

Then register it:

```python
# settings.py
DJANGO_RCLONE = {
    "REMOTE": "myremote:backups",
    "CONNECTOR_MAPPING": {
        "django.db.backends.oracle": "myapp.connectors.OracleConnector",
    },
}
```

Or override for a specific database alias:

```python
DJANGO_RCLONE = {
    "REMOTE": "myremote:backups",
    "CONNECTORS": {
        "legacy_db": "myapp.connectors.OracleConnector",
    },
}
```

### Connector interface

Your connector must implement three things:

| Member | Type | Description |
|---|---|---|
| `extension` | `property -> str` | File extension for backup files (e.g., `"sql"`, `"dump"`) |
| `dump()` | `method -> Popen` | Return a `subprocess.Popen` with `stdout=PIPE` that streams backup data |
| `restore(stdin)` | `method -> Popen` | Return a `subprocess.Popen` with `stdin` set to the provided pipe |

The base class provides properties extracted from Django's `DATABASES` settings: `name`, `host`, `port`, `user`, `password`.

### Security guidelines

When writing custom connectors:

- **Never pass passwords as command-line arguments.** Use environment variables (`PGPASSWORD`, `MYSQL_PWD`) or authentication files (`.pgpass`, `.my.cnf`).
- **Always use `subprocess.PIPE`** for stdout (dump) and stdin (restore) to enable streaming.
- **Return the Popen object** -- don't call `communicate()` or `wait()`. The management command handles process lifecycle.
