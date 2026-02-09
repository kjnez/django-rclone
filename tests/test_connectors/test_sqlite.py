from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from django_rclone.db.sqlite import SqliteConnector
from django_rclone.exceptions import ConnectorError


class TestSqliteConnector:
    def test_extension(self):
        connector = SqliteConnector({"NAME": "/tmp/test.db"})
        assert connector.extension == "sqlite3"

    @patch("django_rclone.db.sqlite.subprocess.Popen")
    def test_create_dump(self, mock_popen: MagicMock):
        connector = SqliteConnector({"NAME": "/tmp/test.db"})

        connector.dump()

        cmd = mock_popen.call_args[0][0]
        assert cmd == ["sqlite3", "/tmp/test.db", ".dump"]
        assert mock_popen.call_args[1]["stdout"] == subprocess.PIPE

    @patch("django_rclone.db.sqlite.subprocess.Popen")
    def test_restore_dump(self, mock_popen: MagicMock):
        connector = SqliteConnector({"NAME": "/tmp/test.db"})
        stdin_mock = MagicMock()

        connector.restore(stdin=stdin_mock)

        cmd = mock_popen.call_args[0][0]
        assert cmd == ["sqlite3", "/tmp/test.db"]
        assert mock_popen.call_args[1]["stdin"] is stdin_mock

    @patch("django_rclone.db.sqlite.subprocess.Popen")
    def test_dump_missing_binary_raises_connector_error(self, mock_popen: MagicMock):
        mock_popen.side_effect = FileNotFoundError(2, "No such file or directory", "sqlite3")
        connector = SqliteConnector({"NAME": "/tmp/test.db"})

        with pytest.raises(ConnectorError, match="not found"):
            connector.dump()

    @patch("django_rclone.db.sqlite.subprocess.Popen")
    def test_restore_oserror_raises_connector_error(self, mock_popen: MagicMock):
        mock_popen.side_effect = OSError(13, "Permission denied")
        connector = SqliteConnector({"NAME": "/tmp/test.db"})

        with pytest.raises(ConnectorError, match="Permission denied"):
            connector.restore(stdin=MagicMock())
