# Configuration

All django-rclone settings live under a single `DJANGO_RCLONE` dictionary in your Django settings module. Any key not provided falls back to its default value.

## Full reference

```python
DJANGO_RCLONE = {
    # Required
    "REMOTE": "",                          # rclone remote:path for backups

    # rclone binary
    "RCLONE_BINARY": "rclone",             # Path to the rclone binary
    "RCLONE_CONFIG": None,                 # Path to rclone.conf (None = rclone default)
    "RCLONE_FLAGS": [],                    # Extra global flags passed to every rclone call

    # Database backups
    "DB_BACKUP_DIR": "db",                 # Subdirectory under REMOTE for DB backups
    "DB_FILENAME_TEMPLATE": "{database}-{datetime}.{ext}",
    "DB_DATE_FORMAT": "%Y-%m-%d-%H%M%S",
    "DB_CLEANUP_KEEP": 10,                 # Number of most recent backups to keep per database

    # Media backups
    "MEDIA_BACKUP_DIR": "media",           # Subdirectory under REMOTE for media backups

    # Connector overrides
    "CONNECTORS": {},                      # Per-database connector class (dotted path)
    "CONNECTOR_MAPPING": {},               # Engine-to-connector class mapping overrides
}
```

## Setting details

### `REMOTE` (required)

The rclone remote and path where backups are stored. This follows rclone's standard `remote:path` notation.

```python
# S3 bucket
"REMOTE": "s3:my-backup-bucket/django-backups"

# Google Cloud Storage
"REMOTE": "gcs:my-bucket/backups"

# SFTP server
"REMOTE": "mysftp:backups/production"

# Local filesystem
"REMOTE": "local:/var/backups/myproject"
```

Database backups are stored under `REMOTE/DB_BACKUP_DIR/` and media backups under `REMOTE/MEDIA_BACKUP_DIR/`.

For provider-specific configuration notes (e.g., Cloudflare R2 requires `no_check_bucket = true`), see [Storage Providers](providers.md).

### `RCLONE_BINARY`

Path to the rclone executable. Defaults to `"rclone"`, which expects rclone to be on your `PATH`. Set this if rclone is installed in a non-standard location:

```python
"RCLONE_BINARY": "/usr/local/bin/rclone"
```

### `RCLONE_CONFIG`

Path to a specific rclone configuration file. When `None` (the default), rclone uses its default config location (`~/.config/rclone/rclone.conf` on Linux).

```python
"RCLONE_CONFIG": "/etc/rclone/production.conf"
```

### `RCLONE_FLAGS`

A list of additional flags passed to every rclone invocation. Useful for setting global options like verbosity, bandwidth limits, or transfer settings:

```python
"RCLONE_FLAGS": [
    "--verbose",
    "--bwlimit", "10M",
    "--transfers", "4",
]
```

### `DB_BACKUP_DIR`

Subdirectory under `REMOTE` where database backups are stored. Defaults to `"db"`.

With `REMOTE = "s3:my-bucket/backups"` and `DB_BACKUP_DIR = "db"`, backups are written to `s3:my-bucket/backups/db/`.

### `DB_FILENAME_TEMPLATE`

Python format string for backup filenames. Available variables:

| Variable | Description | Example |
|---|---|---|
| `{database}` | Django database alias | `default` |
| `{datetime}` | Formatted timestamp (see `DB_DATE_FORMAT`) | `2024-01-15-120000` |
| `{ext}` | File extension from the connector | `dump`, `sqlite3` |

Default: `"{database}-{datetime}.{ext}"`

Example output: `default-2024-01-15-120000.dump`

Constraints:

- Must start with `{database}`.
- Must include a separator immediately after `{database}` (for example `-`).
- Must render a filename (no `/` path separators).

### `DB_DATE_FORMAT`

Python `strftime` format string for the `{datetime}` variable in filenames. Default: `"%Y-%m-%d-%H%M%S"`.

### `DB_CLEANUP_KEEP`

When the `dbbackup --clean` flag is used, this controls how many recent backups to keep per database. Older backups beyond this count are deleted. Default: `10`.

### `MEDIA_BACKUP_DIR`

Subdirectory under `REMOTE` where media files are synced. Defaults to `"media"`.

### `CONNECTORS`

Override the connector class used for a specific database alias. Values are dotted Python paths to connector classes:

```python
"CONNECTORS": {
    "default": "myapp.connectors.CustomPgConnector",
    "analytics": "myapp.connectors.CustomSqliteConnector",
}
```

This takes priority over engine-based mapping.

### `CONNECTOR_MAPPING`

Override which connector class is used for a given database engine. Merges with (and overrides) the built-in mapping:

```python
"CONNECTOR_MAPPING": {
    "django.db.backends.postgresql": "myapp.connectors.CustomPgConnector",
}
```

Built-in mapping:

| Engine | Connector |
|---|---|
| `django.db.backends.postgresql` | `django_rclone.db.postgresql.PgDumpConnector` |
| `django.db.backends.sqlite3` | `django_rclone.db.sqlite.SqliteConnector` |

## Encryption and compression

django-rclone deliberately does not implement encryption or compression in Python. Instead, configure these features at the rclone level.

### Encryption

Create a [crypt remote](https://rclone.org/crypt/) that wraps your storage remote:

```bash
rclone config create myremote-encrypted crypt \
    remote=myremote:backups \
    password=$(rclone obscure your-password)
```

Then use the encrypted remote in your Django settings:

```python
DJANGO_RCLONE = {
    "REMOTE": "myremote-encrypted:",
}
```

All data is transparently encrypted before reaching the storage backend and decrypted on read.

### Compression

Create a [compress remote](https://rclone.org/compress/) that wraps your storage remote:

```bash
rclone config create myremote-compressed compress \
    remote=myremote:backups
```

Or combine encryption and compression by stacking remotes:

```bash
# First compress, then encrypt
rclone config create myremote-compressed compress remote=myremote:backups
rclone config create myremote-secure crypt remote=myremote-compressed:
```

```python
DJANGO_RCLONE = {
    "REMOTE": "myremote-secure:",
}
```

## Environment-specific configuration

A common pattern is to vary the remote by environment:

```python
import os

DJANGO_RCLONE = {
    "REMOTE": os.environ.get("BACKUP_REMOTE", "local:/tmp/backups"),
}
```

Or use separate rclone configs per environment:

```python
DJANGO_RCLONE = {
    "REMOTE": "backups:",
    "RCLONE_CONFIG": f"/etc/rclone/{ENVIRONMENT}.conf",
}
```
