from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from django_rclone.db.base import BaseConnector
from django_rclone.db.mongodb import MongoDumpConnector
from django_rclone.db.mysql import MysqlDumpConnector
from django_rclone.db.postgresql import PgDumpConnector, PgDumpGisConnector
from django_rclone.db.registry import get_connector
from django_rclone.db.sqlite import SqliteConnector
from django_rclone.exceptions import ConnectorError, ConnectorNotFound


class TestBaseConnector:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BaseConnector({"NAME": "test"})

    def test_properties(self):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "5432",
            "USER": "admin",
            "PASSWORD": "secret",
        }

        class DummyConnector(BaseConnector):
            @property
            def extension(self) -> str:
                return "sql"

            def dump(self):
                pass

            def restore(self, stdin=None):
                pass

        c = DummyConnector(settings)
        assert c.name == "mydb"
        assert c.host == "localhost"
        assert c.port == "5432"
        assert c.user == "admin"
        assert c.password == "secret"


class TestSqliteConnector:
    def test_extension(self):
        c = SqliteConnector({"NAME": "/tmp/test.db"})
        assert c.extension == "sqlite3"

    @patch("django_rclone.db.sqlite.subprocess.Popen")
    def test_dump(self, mock_popen):
        c = SqliteConnector({"NAME": "/tmp/test.db"})
        c.dump()
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["sqlite3", "/tmp/test.db", ".dump"]
        assert mock_popen.call_args[1]["stdout"] == subprocess.PIPE

    @patch("django_rclone.db.sqlite.subprocess.Popen")
    def test_restore(self, mock_popen):
        c = SqliteConnector({"NAME": "/tmp/test.db"})
        stdin_mock = MagicMock()
        c.restore(stdin=stdin_mock)
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["sqlite3", "/tmp/test.db"]
        assert mock_popen.call_args[1]["stdin"] is stdin_mock


class TestPgDumpConnector:
    def test_extension(self):
        c = PgDumpConnector({"NAME": "mydb"})
        assert c.extension == "dump"

    def test_env_has_pgpassword(self):
        c = PgDumpConnector({"NAME": "mydb", "PASSWORD": "secret", "HOST": "", "PORT": "", "USER": ""})
        env = c._env()
        assert env["PGPASSWORD"] == "secret"

    def test_env_no_password(self):
        c = PgDumpConnector({"NAME": "mydb", "PASSWORD": "", "HOST": "", "PORT": "", "USER": ""})
        env = c._env()
        assert "PGPASSWORD" not in env

    def test_common_args(self):
        c = PgDumpConnector(
            {
                "NAME": "mydb",
                "HOST": "db.example.com",
                "PORT": "5433",
                "USER": "admin",
                "PASSWORD": "",
            }
        )
        args = c._common_args()
        assert args == ["-h", "db.example.com", "-p", "5433", "-U", "admin"]

    def test_common_args_empty(self):
        c = PgDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})
        assert c._common_args() == []

    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_dump(self, mock_popen):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "5432",
            "USER": "admin",
            "PASSWORD": "secret",
        }
        c = PgDumpConnector(settings)
        c.dump()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "pg_dump"
        assert "--format=custom" in cmd
        assert "mydb" in cmd
        assert mock_popen.call_args[1]["env"]["PGPASSWORD"] == "secret"

    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_restore(self, mock_popen):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "5432",
            "USER": "admin",
            "PASSWORD": "secret",
        }
        c = PgDumpConnector(settings)
        stdin_mock = MagicMock()
        c.restore(stdin=stdin_mock)
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "pg_restore"
        assert "--no-owner" in cmd
        assert "-d" in cmd
        assert mock_popen.call_args[1]["stdin"] is stdin_mock


class TestPgDumpGisConnector:
    def test_extension(self):
        c = PgDumpGisConnector({"NAME": "mydb"})
        assert c.extension == "dump"

    def test_is_subclass_of_pgdump(self):
        assert issubclass(PgDumpGisConnector, PgDumpConnector)

    @patch("django_rclone.db.postgresql.subprocess.run")
    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_restore_enables_postgis_when_admin_user_set(self, mock_popen, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        c = PgDumpGisConnector(
            {
                "NAME": "geodb",
                "HOST": "localhost",
                "PORT": "5432",
                "USER": "app",
                "PASSWORD": "secret",
                "ADMIN_USER": "postgres",
            }
        )
        c.restore(stdin=None)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "psql" in cmd
        assert "CREATE EXTENSION IF NOT EXISTS postgis;" in cmd
        assert "-U" in cmd
        assert "postgres" in cmd

    @patch("django_rclone.db.postgresql.subprocess.run")
    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_restore_skips_postgis_without_admin_user(self, mock_popen, mock_run):
        c = PgDumpGisConnector(
            {
                "NAME": "geodb",
                "HOST": "",
                "PORT": "",
                "USER": "",
                "PASSWORD": "",
            }
        )
        c.restore(stdin=None)
        mock_run.assert_not_called()

    @patch("django_rclone.db.postgresql.subprocess.run")
    @patch("django_rclone.db.postgresql.subprocess.Popen")
    def test_restore_raises_when_postgis_enablement_fails(self, mock_popen, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=b"",
            stderr=b"permission denied",
        )
        c = PgDumpGisConnector(
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
            c.restore(stdin=None)
        mock_popen.assert_not_called()


class TestMysqlDumpConnector:
    def test_extension(self):
        c = MysqlDumpConnector({"NAME": "mydb"})
        assert c.extension == "sql"

    def test_env_has_mysql_pwd(self):
        c = MysqlDumpConnector({"NAME": "mydb", "PASSWORD": "secret", "HOST": "", "PORT": "", "USER": ""})
        env = c._env()
        assert env["MYSQL_PWD"] == "secret"

    def test_env_no_password(self):
        c = MysqlDumpConnector({"NAME": "mydb", "PASSWORD": "", "HOST": "", "PORT": "", "USER": ""})
        env = c._env()
        assert "MYSQL_PWD" not in env

    def test_common_args(self):
        c = MysqlDumpConnector(
            {
                "NAME": "mydb",
                "HOST": "db.example.com",
                "PORT": "3306",
                "USER": "admin",
                "PASSWORD": "",
            }
        )
        args = c._common_args()
        assert args == ["--host", "db.example.com", "--port", "3306", "--user", "admin"]

    def test_common_args_empty(self):
        c = MysqlDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})
        assert c._common_args() == []

    @patch("django_rclone.db.mysql.subprocess.Popen")
    def test_dump(self, mock_popen):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "3306",
            "USER": "admin",
            "PASSWORD": "secret",
        }
        c = MysqlDumpConnector(settings)
        c.dump()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "mysqldump"
        assert "--quick" in cmd
        assert "mydb" in cmd
        assert mock_popen.call_args[1]["env"]["MYSQL_PWD"] == "secret"

    @patch("django_rclone.db.mysql.subprocess.Popen")
    def test_restore(self, mock_popen):
        settings = {
            "NAME": "mydb",
            "HOST": "localhost",
            "PORT": "3306",
            "USER": "admin",
            "PASSWORD": "secret",
        }
        c = MysqlDumpConnector(settings)
        stdin_mock = MagicMock()
        c.restore(stdin=stdin_mock)
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "mysql"
        assert "mydb" in cmd
        assert mock_popen.call_args[1]["stdin"] is stdin_mock


class TestMongoDumpConnector:
    def test_extension(self):
        c = MongoDumpConnector({"NAME": "mydb"})
        assert c.extension == "archive"

    def test_host_port_defaults(self):
        c = MongoDumpConnector({"NAME": "mydb", "HOST": "", "PORT": ""})
        assert c._host_port() == "localhost:27017"

    def test_host_port_custom(self):
        c = MongoDumpConnector({"NAME": "mydb", "HOST": "mongo.example.com", "PORT": "27018"})
        assert c._host_port() == "mongo.example.com:27018"

    def test_auth_args_with_credentials(self):
        c = MongoDumpConnector(
            {
                "NAME": "mydb",
                "HOST": "",
                "PORT": "",
                "USER": "admin",
                "PASSWORD": "secret",
                "AUTH_SOURCE": "admin",
            }
        )
        args = c._auth_args()
        assert args == ["--username", "admin", "--password", "secret", "--authenticationDatabase", "admin"]

    def test_auth_args_no_credentials(self):
        c = MongoDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})
        assert c._auth_args() == []

    @patch("django_rclone.db.mongodb.subprocess.Popen")
    def test_dump(self, mock_popen):
        settings = {
            "NAME": "mydb",
            "HOST": "mongo.example.com",
            "PORT": "27018",
            "USER": "",
            "PASSWORD": "",
        }
        c = MongoDumpConnector(settings)
        c.dump()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "mongodump"
        assert "--db" in cmd
        assert "mydb" in cmd
        assert "--archive" in cmd
        assert "--host" in cmd
        assert "mongo.example.com:27018" in cmd
        assert mock_popen.call_args[1]["stdout"] == subprocess.PIPE

    @patch("django_rclone.db.mongodb.subprocess.Popen")
    def test_restore(self, mock_popen):
        c = MongoDumpConnector({"NAME": "mydb", "HOST": "", "PORT": "", "USER": "", "PASSWORD": ""})
        stdin_mock = MagicMock()
        c.restore(stdin=stdin_mock)
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "mongorestore"
        assert "--drop" in cmd
        assert "--archive" in cmd
        assert mock_popen.call_args[1]["stdin"] is stdin_mock


class TestRegistry:
    def test_get_sqlite_connector(self):
        connector = get_connector("default")
        assert isinstance(connector, SqliteConnector)

    def test_unknown_engine_raises(self):
        with override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.oracle", "NAME": "test"}}):
            with pytest.raises(ConnectorNotFound) as exc_info:
                get_connector("default")
            assert "oracle" in str(exc_info.value)

    def test_custom_connector_mapping(self):
        with override_settings(
            DJANGO_RCLONE={
                "REMOTE": "r:b",
                "CONNECTOR_MAPPING": {
                    "django.db.backends.sqlite3": "django_rclone.db.postgresql.PgDumpConnector",
                },
            }
        ):
            connector = get_connector("default")
            assert isinstance(connector, PgDumpConnector)

    def test_per_database_override(self):
        with override_settings(
            DJANGO_RCLONE={
                "REMOTE": "r:b",
                "CONNECTORS": {
                    "default": "django_rclone.db.postgresql.PgDumpConnector",
                },
            }
        ):
            connector = get_connector("default")
            assert isinstance(connector, PgDumpConnector)

    def test_mysql_engine_mapping(self):
        with override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.mysql", "NAME": "test"}}):
            connector = get_connector("default")
            assert isinstance(connector, MysqlDumpConnector)

    def test_postgis_engine_mapping(self):
        with override_settings(
            DATABASES={"default": {"ENGINE": "django.contrib.gis.db.backends.postgis", "NAME": "test"}}
        ):
            connector = get_connector("default")
            assert isinstance(connector, PgDumpGisConnector)

    def test_djongo_engine_mapping(self):
        with override_settings(DATABASES={"default": {"ENGINE": "djongo", "NAME": "test"}}):
            connector = get_connector("default")
            assert isinstance(connector, MongoDumpConnector)

    def test_prometheus_postgresql_mapping(self):
        with override_settings(
            DATABASES={"default": {"ENGINE": "django_prometheus.db.backends.postgresql", "NAME": "test"}}
        ):
            connector = get_connector("default")
            assert isinstance(connector, PgDumpConnector)

    def test_spatialite_mapping(self):
        with override_settings(
            DATABASES={"default": {"ENGINE": "django.contrib.gis.db.backends.spatialite", "NAME": "test"}}
        ):
            connector = get_connector("default")
            assert isinstance(connector, SqliteConnector)
