from __future__ import annotations

from typing import Any

from django.conf import settings as django_settings

from ..exceptions import ConnectorNotFound
from ..settings import get_setting
from .base import BaseConnector

DEFAULT_CONNECTOR_MAPPING: dict[str, str] = {
    # PostgreSQL
    "django.db.backends.postgresql": "django_rclone.db.postgresql.PgDumpConnector",
    # SQLite
    "django.db.backends.sqlite3": "django_rclone.db.sqlite.SqliteConnector",
    # MySQL / MariaDB
    "django.db.backends.mysql": "django_rclone.db.mysql.MysqlDumpConnector",
    # PostGIS
    "django.contrib.gis.db.backends.postgis": "django_rclone.db.postgresql.PgDumpGisConnector",
    # SpatiaLite
    "django.contrib.gis.db.backends.spatialite": "django_rclone.db.sqlite.SqliteConnector",
    # GIS MySQL
    "django.contrib.gis.db.backends.mysql": "django_rclone.db.mysql.MysqlDumpConnector",
    # MongoDB (djongo / django-mongodb-engine)
    "djongo": "django_rclone.db.mongodb.MongoDumpConnector",
    "django_mongodb_engine": "django_rclone.db.mongodb.MongoDumpConnector",
    # django-prometheus wrappers
    "django_prometheus.db.backends.postgresql": "django_rclone.db.postgresql.PgDumpConnector",
    "django_prometheus.db.backends.sqlite3": "django_rclone.db.sqlite.SqliteConnector",
    "django_prometheus.db.backends.mysql": "django_rclone.db.mysql.MysqlDumpConnector",
    "django_prometheus.db.backends.postgis": "django_rclone.db.postgresql.PgDumpGisConnector",
}


def _import_connector(dotted_path: str) -> type[BaseConnector]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_connector(database: str = "default") -> BaseConnector:
    """Get a database connector instance for the given database alias."""
    db_settings: dict[str, Any] = django_settings.DATABASES[database]
    engine: str = db_settings["ENGINE"]

    # Check for per-database connector overrides
    connectors: dict[str, str] = get_setting("CONNECTORS")  # type: ignore[assignment]
    if database in connectors:
        cls = _import_connector(connectors[database])
        return cls(db_settings)

    # Check for engine→connector mapping overrides
    mapping: dict[str, str] = get_setting("CONNECTOR_MAPPING")  # type: ignore[assignment]
    merged = {**DEFAULT_CONNECTOR_MAPPING, **mapping}

    if engine not in merged:
        raise ConnectorNotFound(engine)

    cls = _import_connector(merged[engine])
    return cls(db_settings)
