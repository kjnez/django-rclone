# Getting Started

This guide walks you through installing django-rclone and running your first backup.

## Prerequisites

- **Python 3.13+**
- **Django 4.2+**
- **rclone** installed on your system ([installation guide](https://rclone.org/install/))

Verify rclone is available:

```bash
rclone version
```

## Install django-rclone

```bash
pip install django-rclone
```

## Configure rclone

If you haven't already, create an rclone remote. rclone's interactive config makes this straightforward:

```bash
rclone config
```

This walks you through setting up a remote -- S3, Google Cloud Storage, Backblaze B2, SFTP, a local path, or [any of 70+ providers](https://rclone.org/overview/).

For quick local testing, you can create a local remote:

```bash
rclone config create localbackup local
```

This creates a remote called `localbackup` that stores files on the local filesystem.

### Cloudflare R2

For [Cloudflare R2](https://developers.cloudflare.com/r2/), you **must** set `no_check_bucket = true`:

```bash
rclone config create r2_backups s3 \
  provider=Cloudflare \
  access_key_id=YOUR_ACCESS_KEY_ID \
  secret_access_key=YOUR_SECRET_ACCESS_KEY \
  endpoint=https://ACCOUNT_ID.r2.cloudflarestorage.com \
  no_check_bucket=true
```

Find your Account ID in the Cloudflare Dashboard → R2 → Overview. Create an API token in Manage R2 API Tokens with Object Read & Write permissions.

**Important:** The `no_check_bucket = true` setting is required for R2. Without it, you'll get 403 Access Denied errors even with correct permissions.

## Configure Django

Add `django_rclone` to your installed apps and point it at your rclone remote:

```python
# settings.py

INSTALLED_APPS = [
    # ...
    "django_rclone",
]

DJANGO_RCLONE = {
    "REMOTE": "localbackup:/var/backups/myproject",
}
```

The `REMOTE` value follows rclone's `remote:path` format. For the local remote above, this means backups will be written to `/var/backups/myproject/`.

For a cloud remote like S3, it might look like:

```python
DJANGO_RCLONE = {
    "REMOTE": "s3:my-backup-bucket/myproject",
}
```

For Cloudflare R2:

```python
DJANGO_RCLONE = {
    "REMOTE": "r2_backups:my-backup-bucket/django-backups",
}
```

## Run your first backup

```bash
python manage.py dbbackup
```

You should see output like:

```
Backing up database 'default' to db/default-2024-01-15-120000.dump
Backup completed: db/default-2024-01-15-120000.dump
```

## Verify the backup exists

```bash
python manage.py listbackups
```

```
Name                                               Size     Modified
---------------------------------------------------------------------------------------
default-2024-01-15-120000.dump                      24.5 KB  2024-01-15T12:00:00Z
```

## Restore from backup

```bash
python manage.py dbrestore
```

This automatically finds and restores the most recent backup. To restore a specific backup:

```bash
python manage.py dbrestore --input-path default-2024-01-15-120000.dump
```

`dbrestore` prompts for confirmation by default. Use `--noinput` for non-interactive execution.

## Back up media files

If your project uses `MEDIA_ROOT`, you can sync media files to the remote:

```bash
python manage.py mediabackup
```

This uses `rclone sync`, so only changed files are transferred on subsequent runs.

## Next steps

- [Configuration](configuration.md) -- all available settings
- [Commands](commands.md) -- detailed command reference
- [Connectors](connectors.md) -- database connector details
- [Signals](signals.md) -- hook into backup/restore events
- [Migrating from django-dbbackup](migration-from-dbbackup.md) -- switching from django-dbbackup
