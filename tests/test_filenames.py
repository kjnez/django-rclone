from __future__ import annotations

import pytest
from django.core.management.base import CommandError

from django_rclone.filenames import (
    _compile_db_filename_pattern,
    database_from_backup_name,
    validate_db_filename_template,
)


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

    def test_rejects_empty_template(self):
        with pytest.raises(CommandError, match="cannot be empty"):
            validate_db_filename_template("")

    def test_rejects_no_separator_after_database(self):
        with pytest.raises(CommandError, match="must include a separator immediately after"):
            validate_db_filename_template("{database}{datetime}.{ext}")

    def test_rejects_format_conversion(self):
        with pytest.raises(CommandError, match="does not support format conversions"):
            validate_db_filename_template("{database!r}-{datetime}.{ext}")

    def test_rejects_format_specifier(self):
        with pytest.raises(CommandError, match="does not support format conversions"):
            validate_db_filename_template("{database:>10}-{datetime}.{ext}")

    def test_rejects_duplicate_placeholder(self):
        with pytest.raises(CommandError, match="appears more than once"):
            validate_db_filename_template("{database}-{datetime}-{datetime}.{ext}")

    def test_allows_template_with_trailing_literal(self):
        """Template with trailing literal (no placeholder) should be valid."""
        _compile_db_filename_pattern.cache_clear()
        validate_db_filename_template("{database}-backup.sql")

    def test_rejects_conversion_on_non_first_field(self):
        """Ensure format conversion check is hit on a field after {database}."""
        _compile_db_filename_pattern.cache_clear()
        with pytest.raises(CommandError, match="does not support format conversions"):
            validate_db_filename_template("{database}-{datetime!s}.{ext}")


class TestDatabaseFromBackupName:
    def test_extracts_database_from_default_template(self):
        template = "{database}-{datetime}.{ext}"
        assert database_from_backup_name("default-2024-01-15-120000.sqlite3", template) == "default"

    def test_extracts_hyphenated_database_when_datetime_is_constrained(self):
        template = "{database}-{datetime}.{ext}"
        assert (
            database_from_backup_name(
                "foo-bar-2024-01-15-120000.sqlite3",
                template,
                date_format="%Y-%m-%d-%H%M%S",
            )
            == "foo-bar"
        )

    def test_returns_none_for_non_matching_name(self):
        template = "{database}-{datetime}.{ext}"
        assert database_from_backup_name("not-a-backup-name", template) is None
