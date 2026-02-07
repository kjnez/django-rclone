# Migrating from django-dbbackup

django-rclone is designed as a drop-in conceptual replacement for [django-dbbackup](https://github.com/Archmonger/django-dbbackup). The management command names are the same, so the interface is familiar. This guide covers what changes when switching.

## What you can remove

django-dbbackup requires several pieces of infrastructure that django-rclone eliminates:

### Dependencies

```diff
  # requirements.txt
- django-dbbackup
- django-storages  # if only used for backups
- boto3            # if only used for backups via S3 storage
+ django-rclone
```

django-rclone has no Python dependencies beyond Django. Storage, encryption, and compression are handled by the rclone binary.

### Settings

django-dbbackup settings in `settings.py` can be removed entirely:

```diff
- DBBACKUP_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
- DBBACKUP_STORAGE_OPTIONS = {
-     "access_key": "...",
-     "secret_key": "...",
-     "bucket_name": "my-backups",
- }
- DBBACKUP_CLEANUP_KEEP = 10
- DBBACKUP_GPG_RECIPIENT = "backup@example.com"
- DBBACKUP_FILENAME_TEMPLATE = "{databasename}-{servername}-{datetime}.{suffix}"

+ DJANGO_RCLONE = {
+     "REMOTE": "s3:my-backups",
+     "DB_CLEANUP_KEEP": 10,
+ }
```

Storage credentials are now in rclone's config (managed via `rclone config`) rather than in Django settings.

### Installed apps

```diff
  INSTALLED_APPS = [
-     "dbbackup",
+     "django_rclone",
  ]
```

## Command mapping

The command names are identical:

| Command | django-dbbackup | django-rclone |
|---|---|---|
| `dbbackup` | Dumps DB, optionally compresses/encrypts, uploads via Django Storages | Dumps DB, pipes directly to `rclone rcat` |
| `dbrestore` | Downloads via Django Storages, optionally decrypts/decompresses, restores | Streams via `rclone cat` directly into restore |
| `mediabackup` | Tars `MEDIA_ROOT`, uploads archive | `rclone sync` (incremental, no tar) |
| `mediarestore` | Downloads archive, untars to `MEDIA_ROOT` | `rclone sync` (incremental, no untar) |
| `listbackups` | Lists via Django Storages, parses filenames | `rclone lsjson` (structured JSON) |

### Option differences

**dbbackup:**

| django-dbbackup flag | django-rclone equivalent |
|---|---|
| `--database` | `--database` (same) |
| `--clean` | `--clean` (same) |
| `--compress` | Not needed -- use rclone `compress` remote |
| `--encrypt` | Not needed -- use rclone `crypt` remote |
| `--output-filename` | Not directly supported -- use `DB_FILENAME_TEMPLATE` |
| `--servername` | Not supported -- simplify template or add via `DB_FILENAME_TEMPLATE` |

**dbrestore:**

| django-dbbackup flag | django-rclone equivalent |
|---|---|
| `--database` | `--database` (same) |
| `--input-filename` | `--input-path` |
| `--uncompress` | Not needed -- rclone handles transparently |
| `--decrypt` | Not needed -- rclone handles transparently |
| `--noinput` | `--noinput` (same intent; skips restore confirmation prompt) |

Additional restore behavior differences:

- django-rclone asks for confirmation before restore unless `--noinput` is provided.
- If multiple Django databases are configured, django-rclone requires `--database`.

## Encryption migration

django-dbbackup uses GPG for encryption. django-rclone delegates encryption to rclone's `crypt` remote.

**Before (django-dbbackup):**
```python
DBBACKUP_GPG_RECIPIENT = "backup@example.com"
DBBACKUP_GPG_ALWAYS_TRUST = True
```

**After (django-rclone):**
```bash
# Create an encrypted remote wrapping your storage remote
rclone config create myremote-crypt crypt \
    remote=myremote:backups \
    password=$(rclone obscure your-password)
```

```python
DJANGO_RCLONE = {
    "REMOTE": "myremote-crypt:",
}
```

Encryption is now transparent -- all reads and writes through the crypt remote are automatically encrypted/decrypted. No per-command flags needed.

## Compression migration

**Before (django-dbbackup):**
```python
# or --compress flag on each command
DBBACKUP_COMPRESS = True
```

**After (django-rclone):**
```bash
rclone config create myremote-compress compress remote=myremote:backups
```

```python
DJANGO_RCLONE = {
    "REMOTE": "myremote-compress:",
}
```

## Media backup differences

This is the most significant behavioral change.

**django-dbbackup** creates a tar archive of `MEDIA_ROOT` and uploads it as a single file. Every backup is a full copy.

**django-rclone** uses `rclone sync`, which:

- Transfers only files that have changed since the last sync
- Maintains the remote as a mirror of `MEDIA_ROOT` (not an archive)
- Does not create tar files

**Implications:**

- Backup speed improves significantly for large media directories with few changes
- Bandwidth usage drops dramatically after the first backup
- You cannot have multiple point-in-time snapshots of media (the remote is always a mirror of the current state)
- If you need versioned media backups, use rclone's `--backup-dir` flag via `RCLONE_FLAGS`, or configure versioning on your storage backend (e.g., S3 versioning)

## Restoring old django-dbbackup backups

django-rclone cannot directly restore backups created by django-dbbackup, because:

1. django-dbbackup backups may be GPG-encrypted or gzip-compressed with specific wrappers
2. Filename conventions differ
3. Media backups are tar archives, not synced directories

To migrate existing backups, restore them with django-dbbackup first, then create new backups with django-rclone.

## Security improvements

django-rclone addresses a known security concern in django-dbbackup: **database passwords in process listings**.

django-dbbackup passes database credentials as command-line arguments to `pg_dump`, `mysql`, etc. This means passwords are visible to any user on the system via `ps aux`.

django-rclone passes PostgreSQL/MySQL passwords through environment variables (`PGPASSWORD`, `MYSQL_PWD`) instead of CLI arguments.

## Signals migration

Both django-dbbackup and django-rclone provide signals. If you already use dbbackup signals, migrate imports to django-rclone signal names:

```python
from django.dispatch import receiver
from django_rclone.signals import post_db_backup

@receiver(post_db_backup)
def on_backup_complete(sender, database, path, **kwargs):
    # Your custom logic here
    pass
```

See [Signals](signals.md) for the full reference.
