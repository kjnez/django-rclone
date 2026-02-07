from __future__ import annotations

import pytest
from django.core.management.base import CommandError

from django_rclone.filenames import database_from_backup_name, validate_db_filename_template


class TestValidateDbFilenameTemplate:
    def test_allows_default_template(self):
        validate_db_filename_template("{database}-{datetime}.{ext}")

    def test_requires_database_placeholder(self):
        with pytest.raises(CommandError, match="must start with \\{database\\}"):
            validate_db_filename_template("{datetime}.{ext}")

    def test_rejects_unknown_placeholder(self):
        with pytest.raises(CommandError, match="Unsupported placeholder"):
            validate_db_filename_template("{database}-{hostname}.{ext}")

    def test_requires_database_at_start(self):
        with pytest.raises(CommandError, match="must start with \\{database\\}"):
            validate_db_filename_template("{datetime}-{database}.{ext}")


class TestDatabaseFromBackupName:
    def test_extracts_database_from_default_template(self):
        template = "{database}-{datetime}.{ext}"
        assert database_from_backup_name("default-2024-01-15-120000.sqlite3", template) == "default"

    def test_returns_none_for_non_matching_name(self):
        template = "{database}-{datetime}.{ext}"
        assert database_from_backup_name("not-a-backup-name", template) is None
