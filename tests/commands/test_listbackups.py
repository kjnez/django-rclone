from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_rclone.management.commands.listbackups import Command as ListbackupsCommand


class TestListbackupsCommand:
    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_list_database_backups(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Name": "default-2024-01-15-120000.sqlite3", "Size": 1024, "ModTime": "2024-01-15T12:00:00Z"},
        ]
        mock_rclone_cls.return_value = rclone

        call_command("listbackups", verbosity=0)

        rclone.lsjson.assert_called_once()

    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_list_media_backups(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Path": "photos/img.jpg", "Name": "img.jpg", "Size": 2048, "ModTime": "2024-01-15T12:00:00Z"},
        ]
        mock_rclone_cls.return_value = rclone

        call_command("listbackups", media=True, verbosity=0)

        rclone.lsjson.assert_called_once()

    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_filter_database(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Name": "default-2024-01-15-120000.sqlite3", "Size": 1024, "ModTime": "2024-01-15T12:00:00Z"},
            {"Name": "analytics-2024-01-15-120000.sqlite3", "Size": 512, "ModTime": "2024-01-15T12:00:00Z"},
        ]
        mock_rclone_cls.return_value = rclone

        out = StringIO()
        call_command("listbackups", database="default", stdout=out)

        output = out.getvalue()
        assert "default-2024-01-15-120000.sqlite3" in output
        assert "analytics-2024-01-15-120000.sqlite3" not in output

    @patch("django_rclone.management.commands.listbackups.Rclone")
    @override_settings(
        DJANGO_RCLONE={
            "REMOTE": "testremote:backups",
            "DB_FILENAME_TEMPLATE": "{datetime}-{database}.{ext}",
        }
    )
    def test_invalid_template(self, mock_rclone_cls: MagicMock):
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(CommandError):
            call_command("listbackups", database="default")

    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_no_database_backups(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = []
        mock_rclone_cls.return_value = rclone

        out = StringIO()
        call_command("listbackups", stdout=out)

        assert "No database backups found" in out.getvalue()

    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_no_media_backups(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = []
        mock_rclone_cls.return_value = rclone

        out = StringIO()
        call_command("listbackups", media=True, stdout=out)

        assert "No media backups found" in out.getvalue()


class TestFormatSize:
    def test_bytes(self):
        assert ListbackupsCommand._format_size(512) == "512 B"

    def test_kilobytes(self):
        assert ListbackupsCommand._format_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert ListbackupsCommand._format_size(1024**2) == "1.0 MB"

    def test_gigabytes(self):
        assert ListbackupsCommand._format_size(1024**3) == "1.0 GB"

    def test_terabytes(self):
        assert ListbackupsCommand._format_size(1024**4) == "1.0 TB"

    def test_petabytes(self):
        assert ListbackupsCommand._format_size(1024**5) == "1.0 PB"
