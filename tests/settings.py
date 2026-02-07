SECRET_KEY = "test-secret-key"

INSTALLED_APPS = [
    "django_rclone",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

MEDIA_ROOT = "/tmp/django_rclone_test_media"

DJANGO_RCLONE = {
    "REMOTE": "testremote:backups",
}
