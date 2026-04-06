from copy import deepcopy
from typing import Literal, cast, overload

from django.conf import settings

type SettingValue = str | int | None | list[str] | dict[str, str]
type MutableSettingValue = list[str] | dict[str, str]
type StringSettingKey = Literal[
    "REMOTE",
    "RCLONE_BINARY",
    "DB_BACKUP_DIR",
    "DB_FILENAME_TEMPLATE",
    "DB_DATE_FORMAT",
    "MEDIA_BACKUP_DIR",
]
type DictSettingKey = Literal["CONNECTORS", "CONNECTOR_MAPPING"]
type SettingKey = StringSettingKey | Literal["RCLONE_CONFIG", "RCLONE_FLAGS", "DB_CLEANUP_KEEP"] | DictSettingKey

DEFAULTS: dict[SettingKey, SettingValue] = {
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


def _copy_if_mutable(value: SettingValue) -> SettingValue:
    if isinstance(value, list):
        return cast(MutableSettingValue, deepcopy(value))
    if isinstance(value, dict):
        return cast(MutableSettingValue, deepcopy(value))
    return value


@overload
def get_setting(key: StringSettingKey) -> str: ...


@overload
def get_setting(key: Literal["RCLONE_CONFIG"]) -> str | None: ...


@overload
def get_setting(key: Literal["RCLONE_FLAGS"]) -> list[str]: ...


@overload
def get_setting(key: Literal["DB_CLEANUP_KEEP"]) -> int: ...


@overload
def get_setting(key: DictSettingKey) -> dict[str, str]: ...


@overload
def get_setting(key: str) -> SettingValue: ...


def get_setting(key: str) -> SettingValue:
    """Get a django-rclone setting, falling back to defaults."""
    user_settings = cast(dict[SettingKey, SettingValue], getattr(settings, "DJANGO_RCLONE", {}))
    if key in user_settings:
        return _copy_if_mutable(user_settings[cast(SettingKey, key)])
    if key in DEFAULTS:
        return _copy_if_mutable(DEFAULTS[cast(SettingKey, key)])
    msg = f"Unknown django-rclone setting: {key}"
    raise KeyError(msg)
