from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from django_rclone.db.mysql import MysqlDumpConnector
from django_rclone.exceptions import ConnectorError


class TestMysqlDumpConnector:
    def test_extension(self):
        connector = MysqlDumpConnector({"NAME": "mydb"})
        assert connector.extension == "sql"

    def test_env_uses_mysql_pwd(self):
        connector = MysqlDumpConnector({"NAME": "mydb", "PASSWORD": "secret", "HOST": "", "PORT": "", "USER": ""})
        env = connector._env()
        assert env["MYSQL_PWD"] == "secret"

    def test_env_without_password(self):
        connector = MysqlDumpConnector({"NAME": "mydb", "PASSWORD": "", "HOST": "", "PORT": "", "USER": ""})
        env = connector._env()
        assert "MYSQL_PWD" not in env

    def test_common_args(self):
        connector = MysqlDumpConnector(
            {
                "NAME": "mydb",
                "HOST": "db.example.com",
                "PORT": "3306",
                "USER": "admin",
                "PASSWORD": "",
            }
        )
        assert connector._common_args() == ["--host", "db.example.com", "--port", "3306", "--user", "admin"]

    def test_common_args_empty(self):
        connector = MysqlDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})
        assert connector._common_args() == []

    @patch("django_rclone.db.mysql.subprocess.Popen")
    def test_create_dump(self, mock_popen: MagicMock):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "3306",
            "USER": "admin",
            "PASSWORD": "secret",
        }
        connector = MysqlDumpConnector(settings)

        connector.dump()

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "mysqldump"
        assert "--quick" in cmd
        assert "mydb" in cmd
        assert mock_popen.call_args[1]["env"]["MYSQL_PWD"] == "secret"
        assert mock_popen.call_args[1]["stdout"] == subprocess.PIPE

    @patch("django_rclone.db.mysql.subprocess.Popen")
    def test_restore_dump(self, mock_popen: MagicMock):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "3306",
            "USER": "admin",
            "PASSWORD": "secret",
        }
        connector = MysqlDumpConnector(settings)
        stdin_mock = MagicMock()

        connector.restore(stdin=stdin_mock)

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "mysql"
        assert "mydb" in cmd
        assert mock_popen.call_args[1]["stdin"] is stdin_mock

    @patch("django_rclone.db.mysql.subprocess.Popen")
    def test_dump_missing_binary_raises_connector_error(self, mock_popen: MagicMock):
        mock_popen.side_effect = FileNotFoundError(2, "No such file or directory", "mysqldump")
        connector = MysqlDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})

        with pytest.raises(ConnectorError, match="not found"):
            connector.dump()

    @patch("django_rclone.db.mysql.subprocess.Popen")
    def test_restore_oserror_raises_connector_error(self, mock_popen: MagicMock):
        mock_popen.side_effect = OSError(13, "Permission denied")
        connector = MysqlDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})

        with pytest.raises(ConnectorError, match="Permission denied"):
            connector.restore(stdin=MagicMock())
