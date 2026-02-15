from __future__ import annotations

import os
import shutil
import subprocess
from contextlib import suppress
from copy import deepcopy
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.db import connections
from django.test.utils import override_settings

SQLITE_ALIAS = "integration_sqlite"
POSTGRES_ALIAS = "integration_postgres"
MYSQL_ALIAS = "integration_mysql"

SQLITE_NAME = os.environ.get("TEST_SQLITE_NAME", "/tmp/django_rclone_integration.sqlite3")
PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
PG_PORT = os.environ.get("TEST_PG_PORT", "5432")
PG_USER = os.environ.get("TEST_PG_USER", "django_rclone")
PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "testpassword")
PG_NAME = os.environ.get("TEST_PG_NAME", "django_rclone_test")
MYSQL_HOST = os.environ.get("TEST_MYSQL_HOST", "localhost")
MYSQL_PORT = os.environ.get("TEST_MYSQL_PORT", "3306")
MYSQL_USER = os.environ.get("TEST_MYSQL_USER", "django_rclone")
MYSQL_PASSWORD = os.environ.get("TEST_MYSQL_PASSWORD", "testpassword")
MYSQL_NAME = os.environ.get("TEST_MYSQL_NAME", "django_rclone_test")
# mysqlclient treats "localhost" as a Unix socket; force TCP defaults for Docker.
if MYSQL_HOST == "localhost":
    MYSQL_HOST = "127.0.0.1"

BASE_DATABASES = deepcopy(django_settings.DATABASES)

SQLITE_SETTINGS = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": SQLITE_NAME,
}
PG_SETTINGS = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": PG_NAME,
    "USER": PG_USER,
    "PASSWORD": PG_PASSWORD,
    "HOST": PG_HOST,
    "PORT": PG_PORT,
}
MYSQL_SETTINGS = {
    "ENGINE": "django.db.backends.mysql",
    "NAME": MYSQL_NAME,
    "USER": MYSQL_USER,
    "PASSWORD": MYSQL_PASSWORD,
    "HOST": MYSQL_HOST,
    "PORT": MYSQL_PORT,
}

# ---------------------------------------------------------------------------
# Skip markers — probe real connectivity
# ---------------------------------------------------------------------------


def _pg_available() -> bool:
    try:
        import psycopg  # noqa: F401
    except ImportError:
        try:
            import psycopg2  # noqa: F401
        except ImportError:
            return False

    if not shutil.which("pg_dump"):
        return False
    if not shutil.which("pg_isready"):
        return False
    try:
        cmd = ["pg_isready"]
        if PG_HOST:
            cmd.extend(["-h", PG_HOST])
        if PG_PORT:
            cmd.extend(["-p", PG_PORT])
        if PG_USER:
            cmd.extend(["-U", PG_USER])
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _mysql_available() -> bool:
    try:
        import MySQLdb  # noqa: F401
    except ImportError:
        try:
            import pymysql  # noqa: F401
        except ImportError:
            return False

    if not shutil.which("mysqldump"):
        return False
    if not shutil.which("mysqladmin"):
        return False
    try:
        env = os.environ.copy()
        env["MYSQL_PWD"] = MYSQL_PASSWORD
        cmd = ["mysqladmin", "ping"]
        if MYSQL_HOST:
            cmd.extend(["-h", MYSQL_HOST])
        if MYSQL_PORT:
            cmd.extend(["-P", MYSQL_PORT])
        if MYSQL_USER:
            cmd.extend(["-u", MYSQL_USER])
        result = subprocess.run(
            cmd,
            capture_output=True,
            env=env,
            timeout=5,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _rclone_available() -> bool:
    return shutil.which("rclone") is not None


def _sqlite3_available() -> bool:
    return shutil.which("sqlite3") is not None


requires_postgres = pytest.mark.skipif(not _pg_available(), reason="PostgreSQL not available")
requires_mysql = pytest.mark.skipif(not _mysql_available(), reason="MySQL not available")
requires_rclone = pytest.mark.skipif(not _rclone_available(), reason="rclone not available")
requires_sqlite3 = pytest.mark.skipif(not _sqlite3_available(), reason="sqlite3 CLI not available")


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


def _integration_databases() -> dict[str, dict[str, object]]:
    databases = deepcopy(BASE_DATABASES)
    databases[SQLITE_ALIAS] = deepcopy(SQLITE_SETTINGS)
    databases[POSTGRES_ALIAS] = deepcopy(PG_SETTINGS)
    databases[MYSQL_ALIAS] = deepcopy(MYSQL_SETTINGS)
    return databases


def _refresh_connection_handler() -> None:
    connections.close_all()
    with suppress(AttributeError):
        del connections.settings
    connections._settings = None
    aliases = set(getattr(django_settings, "DATABASES", {}))
    aliases.update({SQLITE_ALIAS, POSTGRES_ALIAS, MYSQL_ALIAS})
    for alias in aliases:
        with suppress(AttributeError):
            del connections[alias]


@pytest.fixture()
def rclone_local_remote(tmp_path):
    """Provide a temp directory as a local rclone remote (no config needed)."""
    return str(tmp_path / "rclone_remote")


@pytest.fixture()
def setup_sqlite_db(rclone_local_remote, django_db_blocker):
    """Set up the static SQLite integration alias with migrations applied."""
    from django.core.management import call_command

    db_name = str(SQLITE_NAME)
    if db_name and db_name != ":memory:":
        Path(db_name).unlink(missing_ok=True)

    django_rclone_settings = {"REMOTE": rclone_local_remote}
    with django_db_blocker.unblock():
        with override_settings(DATABASES=_integration_databases(), DJANGO_RCLONE=django_rclone_settings):
            _refresh_connection_handler()
            call_command("migrate", database=SQLITE_ALIAS, verbosity=0)
            yield SQLITE_ALIAS

            from tests.testapp.models import Entry

            Entry.objects.using(SQLITE_ALIAS).all().delete()
            connections[SQLITE_ALIAS].close()
        _refresh_connection_handler()

    if db_name and db_name != ":memory:":
        Path(db_name).unlink(missing_ok=True)


@pytest.fixture()
def setup_pg_db(rclone_local_remote, django_db_blocker):
    """Set up the static PostgreSQL integration alias with migrations applied."""
    from django.core.management import call_command

    django_rclone_settings = {"REMOTE": rclone_local_remote}
    with django_db_blocker.unblock():
        with override_settings(DATABASES=_integration_databases(), DJANGO_RCLONE=django_rclone_settings):
            _refresh_connection_handler()
            call_command("migrate", database=POSTGRES_ALIAS, verbosity=0)
            yield POSTGRES_ALIAS

            from tests.testapp.models import Entry

            Entry.objects.using(POSTGRES_ALIAS).all().delete()
            connections[POSTGRES_ALIAS].close()
        _refresh_connection_handler()


@pytest.fixture()
def setup_mysql_db(rclone_local_remote, django_db_blocker):
    """Set up the static MySQL integration alias with migrations applied."""
    from django.core.management import call_command

    django_rclone_settings = {"REMOTE": rclone_local_remote}
    with django_db_blocker.unblock():
        with override_settings(DATABASES=_integration_databases(), DJANGO_RCLONE=django_rclone_settings):
            _refresh_connection_handler()
            call_command("migrate", database=MYSQL_ALIAS, verbosity=0)
            yield MYSQL_ALIAS

            from tests.testapp.models import Entry

            Entry.objects.using(MYSQL_ALIAS).all().delete()
            connections[MYSQL_ALIAS].close()
        _refresh_connection_handler()
