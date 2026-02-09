from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.test import override_settings

from django_rclone.db.base import BaseConnector
from django_rclone.db.mongodb import MongoDumpConnector
from django_rclone.db.mysql import MysqlDumpConnector
from django_rclone.db.postgresql import PgDumpConnector, PgDumpGisConnector
from django_rclone.db.registry import get_connector
from django_rclone.db.sqlite import SqliteConnector
from django_rclone.exceptions import ConnectorNotFound


class TestBaseConnector:
    def test_abstract_base(self):
        with pytest.raises(TypeError):
            BaseConnector({"NAME": "test"})

    def test_settings_properties(self):
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
                return MagicMock()

            def restore(self, stdin):
                return MagicMock()

        connector = DummyConnector(settings)
        assert connector.name == "mydb"
        assert connector.host == "localhost"
        assert connector.port == "5432"
        assert connector.user == "admin"
        assert connector.password == "secret"


class TestGetConnector:
    pytestmark = pytest.mark.filterwarnings(
        "ignore:Overriding setting DATABASES can lead to unexpected behavior\\.:UserWarning"
    )

    def test_default_sqlite_mapping(self):
        connector = get_connector("default")
        assert isinstance(connector, SqliteConnector)

    def test_unknown_engine_raises(self):
        with override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.oracle", "NAME": "test"}}):
            with pytest.raises(ConnectorNotFound) as exc_info:
                get_connector("default")
            assert "oracle" in str(exc_info.value)

    def test_custom_engine_mapping(self):
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

    def test_prometheus_engine_mapping(self):
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
