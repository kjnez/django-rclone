import pytest
from django.test import override_settings

from django_rclone.settings import get_setting


class TestGetSetting:
    def test_returns_default(self):
        assert get_setting("RCLONE_BINARY") == "rclone"

    def test_returns_user_override(self):
        with override_settings(DJANGO_RCLONE={"REMOTE": "myremote:path", "RCLONE_BINARY": "/usr/local/bin/rclone"}):
            assert get_setting("RCLONE_BINARY") == "/usr/local/bin/rclone"

    def test_user_setting_takes_precedence(self):
        with override_settings(DJANGO_RCLONE={"REMOTE": "custom:remote", "DB_CLEANUP_KEEP": 5}):
            assert get_setting("REMOTE") == "custom:remote"
            assert get_setting("DB_CLEANUP_KEEP") == 5

    def test_unknown_setting_raises(self):
        with pytest.raises(KeyError, match="Unknown django-rclone setting"):
            get_setting("NONEXISTENT_SETTING")

    def test_defaults(self):
        assert get_setting("DB_BACKUP_DIR") == "db"
        assert get_setting("MEDIA_BACKUP_DIR") == "media"
        assert get_setting("DB_FILENAME_TEMPLATE") == "{database}-{datetime}.{ext}"
        assert get_setting("DB_DATE_FORMAT") == "%Y-%m-%d-%H%M%S"
        assert get_setting("DB_CLEANUP_KEEP") == 10
        assert get_setting("RCLONE_CONFIG") is None
        assert get_setting("RCLONE_FLAGS") == []
        assert get_setting("CONNECTORS") == {}
        assert get_setting("CONNECTOR_MAPPING") == {}

    def test_default_mutable_values_are_copied(self):
        flags: list[str] = get_setting("RCLONE_FLAGS")  # type: ignore[assignment]
        connectors: dict[str, str] = get_setting("CONNECTORS")  # type: ignore[assignment]
        mapping: dict[str, str] = get_setting("CONNECTOR_MAPPING")  # type: ignore[assignment]

        assert isinstance(flags, list)
        assert isinstance(connectors, dict)
        assert isinstance(mapping, dict)

        flags.append("--fast-list")
        connectors["default"] = "django_rclone.db.sqlite.SqliteConnector"
        mapping["django.db.backends.oracle"] = "django_rclone.db.sqlite.SqliteConnector"

        assert get_setting("RCLONE_FLAGS") == []
        assert get_setting("CONNECTORS") == {}
        assert get_setting("CONNECTOR_MAPPING") == {}

    @override_settings(
        DJANGO_RCLONE={
            "REMOTE": "myremote:path",
            "RCLONE_FLAGS": ["--checksum"],
            "CONNECTORS": {"default": "django_rclone.db.sqlite.SqliteConnector"},
        }
    )
    def test_user_mutable_values_are_copied(self):
        flags: list[str] = get_setting("RCLONE_FLAGS")  # type: ignore[assignment]
        connectors: dict[str, str] = get_setting("CONNECTORS")  # type: ignore[assignment]

        assert isinstance(flags, list)
        assert isinstance(connectors, dict)

        flags.append("--fast-list")
        connectors["analytics"] = "django_rclone.db.postgresql.PgDumpConnector"

        assert get_setting("RCLONE_FLAGS") == ["--checksum"]
        assert get_setting("CONNECTORS") == {"default": "django_rclone.db.sqlite.SqliteConnector"}
