from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connections

from tests.testapp.models import Entry

from .conftest import requires_mysql, requires_postgres, requires_rclone, requires_sqlite3

pytestmark = pytest.mark.integration


@requires_sqlite3
@requires_rclone
def test_dbbackup_then_dbrestore_sqlite(setup_sqlite_db):
    """Full backup → delete → restore → verify cycle for SQLite."""
    database = setup_sqlite_db
    entries = Entry.objects.using(database)
    entries.create(name="alpha", value=1)
    entries.create(name="beta", value=2)
    entries.create(name="gamma", value=3)
    assert entries.count() == 3

    call_command("dbbackup", database=database, verbosity=0)

    entries.all().delete()
    assert entries.count() == 0

    db_name = str(settings.DATABASES[database]["NAME"])
    connections[database].close()
    Path(db_name).unlink(missing_ok=True)
    call_command("dbrestore", database=database, interactive=False, verbosity=0)
    connections[database].close()

    assert Entry.objects.using(database).count() == 3
    assert Entry.objects.using(database).filter(name="alpha", value=1).exists()
    assert Entry.objects.using(database).filter(name="beta", value=2).exists()
    assert Entry.objects.using(database).filter(name="gamma", value=3).exists()


@requires_postgres
@requires_rclone
@pytest.mark.requires_postgres
def test_dbbackup_then_dbrestore_postgres(setup_pg_db):
    """Full backup → delete → restore → verify cycle for PostgreSQL."""
    database = setup_pg_db
    entries = Entry.objects.using(database)
    entries.create(name="alpha", value=1)
    entries.create(name="beta", value=2)
    entries.create(name="gamma", value=3)
    assert entries.count() == 3

    call_command("dbbackup", database=database, verbosity=0)

    entries.all().delete()
    assert entries.count() == 0

    call_command("dbrestore", database=database, interactive=False, verbosity=0)
    connections[database].close()

    assert Entry.objects.using(database).count() == 3
    assert Entry.objects.using(database).filter(name="alpha", value=1).exists()
    assert Entry.objects.using(database).filter(name="beta", value=2).exists()
    assert Entry.objects.using(database).filter(name="gamma", value=3).exists()


@requires_mysql
@requires_rclone
@pytest.mark.requires_mysql
def test_dbbackup_then_dbrestore_mysql(setup_mysql_db):
    """Full backup → delete → restore → verify cycle for MySQL."""
    database = setup_mysql_db
    entries = Entry.objects.using(database)
    entries.create(name="alpha", value=1)
    entries.create(name="beta", value=2)
    entries.create(name="gamma", value=3)
    assert entries.count() == 3

    call_command("dbbackup", database=database, verbosity=0)

    entries.all().delete()
    assert entries.count() == 0

    call_command("dbrestore", database=database, interactive=False, verbosity=0)
    connections[database].close()

    assert Entry.objects.using(database).count() == 3
    assert Entry.objects.using(database).filter(name="alpha", value=1).exists()
    assert Entry.objects.using(database).filter(name="beta", value=2).exists()
    assert Entry.objects.using(database).filter(name="gamma", value=3).exists()
