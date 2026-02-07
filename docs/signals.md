# Signals

django-rclone dispatches Django signals before and after each backup and restore operation. Use these to integrate logging, notifications, health checks, or custom pre/post processing.

## Available signals

All signals are importable from `django_rclone.signals`.

### Database signals

| Signal | Sent when | Keyword arguments |
|---|---|---|
| `pre_db_backup` | Before database dump starts | `sender`, `database` |
| `post_db_backup` | After backup is uploaded | `sender`, `database`, `path` |
| `pre_db_restore` | Before restore starts | `sender`, `database`, `path` |
| `post_db_restore` | After restore completes | `sender`, `database` |

### Media signals

| Signal | Sent when | Keyword arguments |
|---|---|---|
| `pre_media_backup` | Before media sync starts | `sender` |
| `post_media_backup` | After media sync completes | `sender` |
| `pre_media_restore` | Before media restore starts | `sender` |
| `post_media_restore` | After media restore completes | `sender` |

## Arguments

- **`sender`** -- The management command class that sent the signal.
- **`database`** -- The Django database alias (e.g., `"default"`).
- **`path`** -- The remote backup file path relative to `DB_BACKUP_DIR` (e.g., `"db/default-2024-01-15-120000.dump"`).

## Examples

### Logging

```python
# myapp/signals.py
import logging
from django.dispatch import receiver
from django_rclone.signals import post_db_backup, post_db_restore

logger = logging.getLogger("backups")

@receiver(post_db_backup)
def log_backup(sender, database, path, **kwargs):
    logger.info("Database '%s' backed up to %s", database, path)

@receiver(post_db_restore)
def log_restore(sender, database, **kwargs):
    logger.info("Database '%s' restored", database)
```

### Slack notification

```python
import requests
from django.dispatch import receiver
from django_rclone.signals import post_db_backup

SLACK_WEBHOOK = "https://hooks.slack.com/services/..."

@receiver(post_db_backup)
def notify_slack(sender, database, path, **kwargs):
    requests.post(SLACK_WEBHOOK, json={
        "text": f"Database `{database}` backed up to `{path}`",
    })
```

### Health check ping

```python
import requests
from django.dispatch import receiver
from django_rclone.signals import post_db_backup

@receiver(post_db_backup)
def ping_healthcheck(sender, **kwargs):
    requests.get("https://hc-ping.com/your-uuid-here")
```

### Pre-backup validation

```python
from django.dispatch import receiver
from django_rclone.signals import pre_db_restore

@receiver(pre_db_restore)
def confirm_restore(sender, database, path, **kwargs):
    if database == "default":
        # Custom safeguard: could check an env var or flag
        import os
        if not os.environ.get("ALLOW_RESTORE"):
            raise RuntimeError("Set ALLOW_RESTORE=1 to restore the production database")
```

## Connecting signals

Signals are connected via either the `@receiver` decorator or the `.connect()` method. If using the decorator, make sure the module is imported at startup -- typically by importing it in your app's `AppConfig.ready()`:

```python
# myapp/apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        import myapp.signals  # noqa: F401
```
