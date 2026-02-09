from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from django_rclone.db.postgresql import PgDumpConnector, PgDumpGisConnector
from django_rclone.exceptions import ConnectorError


class TestPgDumpConnector:
    def test_extension(self):
        connector = PgDumpConnector({"NAME": "mydb"})
        assert connector.extension == "dump"

    def test_env_uses_pgpassword(self):
        connector = PgDumpConnector({"NAME": "mydb", "PASSWORD": "secret", "HOST": "", "PORT": "", "USER": ""})
        env = connector._env()
        assert env["PGPASSWORD"] == "secret"

    def test_env_without_password(self):
        connector = PgDumpConnector({"NAME": "mydb", "PASSWORD": "", "HOST": "", "PORT": "", "USER": ""})
        env = connector._env()
        assert "PGPASSWORD" not in env

    def test_common_args(self):
        connector = PgDumpConnector(
            {
                "NAME": "mydb",
                "HOST": "db.example.com",
                "PORT": "5433",
                "USER": "admin",
                "PASSWORD": "",
            }
        )
        assert connector._common_args() == ["-h", "db.example.com", "-p", "5433", "-U", "admin"]

    def test_common_args_empty(self):
        connector = PgDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})
        assert connector._common_args() == []

    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_create_dump(self, mock_popen: MagicMock):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "5432",
            "USER": "admin",
            "PASSWORD": "secret",
        }
        connector = PgDumpConnector(settings)

        connector.dump()

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "pg_dump"
        assert "--format=custom" in cmd
        assert "--no-password" in cmd
        assert "mydb" in cmd
        assert mock_popen.call_args[1]["env"]["PGPASSWORD"] == "secret"

    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_restore_dump(self, mock_popen: MagicMock):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "5432",
            "USER": "admin",
            "PASSWORD": "secret",
        }
        connector = PgDumpConnector(settings)
        stdin_mock = MagicMock()

        connector.restore(stdin=stdin_mock)

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "pg_restore"
        assert "--no-owner" in cmd
        assert "--clean" in cmd
        assert "--if-exists" in cmd
        assert "--no-password" in cmd
        assert "-d" in cmd
        assert mock_popen.call_args[1]["stdin"] is stdin_mock


class TestPgDumpGisConnector:
    def test_extension(self):
        connector = PgDumpGisConnector({"NAME": "mydb"})
        assert connector.extension == "dump"

    def test_is_subclass(self):
        assert issubclass(PgDumpGisConnector, PgDumpConnector)

    @patch("django_rclone.db.postgresql.subprocess.run")
    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_restore_enables_postgis_with_admin_user(self, mock_popen: MagicMock, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        connector = PgDumpGisConnector(
            {
                "NAME": "geodb",
                "HOST": "localhost",
                "PORT": "5432",
                "USER": "app",
                "PASSWORD": "secret",
                "ADMIN_USER": "postgres",
            }
        )

        connector.restore(stdin=None)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "psql" in cmd
        assert "CREATE EXTENSION IF NOT EXISTS postgis;" in cmd
        assert "-U" in cmd
        assert "postgres" in cmd

    @patch("django_rclone.db.postgresql.subprocess.run")
    def test_enable_postgis_optional_args(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        connector = PgDumpGisConnector(
            {
                "NAME": "geodb",
                "HOST": "",
                "PORT": "",
                "USER": "",
                "PASSWORD": "",
                "ADMIN_USER": "",
            }
        )

        connector._enable_postgis()

        cmd = mock_run.call_args[0][0]
        assert "-U" not in cmd
        assert "-h" not in cmd
        assert "-p" not in cmd

    @patch("django_rclone.db.postgresql.subprocess.run")
    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_restore_skips_postgis_without_admin_user(self, mock_popen: MagicMock, mock_run: MagicMock):
        connector = PgDumpGisConnector(
            {
                "NAME": "geodb",
                "HOST": "",
                "PORT": "",
                "USER": "",
                "PASSWORD": "",
            }
        )

        connector.restore(stdin=None)

        mock_run.assert_not_called()

    @patch("django_rclone.db.postgresql.subprocess.run")
    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_restore_raises_when_postgis_enablement_fails(self, mock_popen: MagicMock, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=b"",
            stderr=b"permission denied",
        )
        connector = PgDumpGisConnector(
            {
                "NAME": "geodb",
                "HOST": "localhost",
                "PORT": "5432",
                "USER": "app",
                "PASSWORD": "secret",
                "ADMIN_USER": "postgres",
            }
        )

        with pytest.raises(ConnectorError, match="Failed to enable PostGIS extension"):
            connector.restore(stdin=None)

        mock_popen.assert_not_called()
