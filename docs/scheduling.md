# Scheduling Backups

django-rclone provides management commands but does not include a built-in scheduler. Use any of the approaches below to run backups on a schedule.

## Celery Beat

If your project already uses [Celery](https://docs.celeryq.dev/), you can schedule backups with [Celery Beat](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html).

### Create Celery tasks

Wrap the management commands as Celery tasks in your app:

```python
# myapp/tasks.py
from celery import shared_task
from django.core.management import call_command


@shared_task
def backup_db():
    call_command("dbbackup", "--clean")


@shared_task
def backup_media():
    call_command("mediabackup")
```

### Configure the beat schedule

Add periodic tasks to your Django settings:

```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "backup-db": {
        "task": "myapp.tasks.backup_db",
        "schedule": crontab(minute="0", hour="2"),  # daily at 02:00
    },
    "backup-media": {
        "task": "myapp.tasks.backup_media",
        "schedule": crontab(minute="0", hour="3"),  # daily at 03:00
    },
}
```

Start the worker and beat scheduler:

```bash
celery -A myproject worker --loglevel=info
celery -A myproject beat --loglevel=info
```

!!! tip

    Connect a [signal](signals.md) like `post_db_backup` to send a notification or ping a health-check endpoint after each backup completes.

## System Crontab

The simplest approach -- no extra dependencies required. Edit your crontab with `crontab -e`:

```crontab
# Database backup daily at 02:00
0 2 * * * /path/to/venv/bin/python /path/to/manage.py dbbackup --clean

# Media backup daily at 03:00
0 3 * * * /path/to/venv/bin/python /path/to/manage.py mediabackup
```

!!! note

    Set `DJANGO_SETTINGS_MODULE` in the crontab environment or pass `--settings` to each command if Django cannot locate your settings automatically.

To capture output for debugging, redirect to a log file:

```crontab
0 2 * * * /path/to/venv/bin/python /path/to/manage.py dbbackup --clean >> /var/log/django-backup.log 2>&1
```

!!! tip

    Use [signals](signals.md) like `post_db_backup` and `post_media_backup` to trigger notifications, logging, or health-check pings regardless of how the commands are invoked.
