from copy import deepcopy

from django.conf import settings

DEFAULTS: dict[str, object] = {
    # Required
    "REMOTE": "",
    # Optional
    "RCLONE_BINARY": "rclone",
    "RCLONE_CONFIG": None,
    "RCLONE_FLAGS": [],
    # Database
    "DB_BACKUP_DIR": "db",
    "DB_FILENAME_TEMPLATE": "{database}-{datetime}.{ext}",
    "DB_DATE_FORMAT": "%Y-%m-%d-%H%M%S",
    "DB_CLEANUP_KEEP": 10,
    # Media
    "MEDIA_BACKUP_DIR": "media",
    # Connectors
    "CONNECTORS": {},
    "CONNECTOR_MAPPING": {},
}


def get_setting(key: str) -> object:
    """Get a django-rclone setting, falling back to defaults."""
    user_settings: dict[str, object] = getattr(settings, "DJANGO_RCLONE", {})
    if key in user_settings:
        value = user_settings[key]
        return deepcopy(value) if isinstance(value, (dict, list, set)) else value
    if key in DEFAULTS:
        value = DEFAULTS[key]
        return deepcopy(value) if isinstance(value, (dict, list, set)) else value
    msg = f"Unknown django-rclone setting: {key}"
    raise KeyError(msg)
