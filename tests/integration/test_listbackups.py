from __future__ import annotations

import io

import pytest
from django.core.management import call_command

from .conftest import requires_rclone, requires_sqlite3

pytestmark = pytest.mark.integration


@requires_sqlite3
@requires_rclone
def test_listbackups_shows_backup(setup_sqlite_db):
    """After a backup, listbackups should show the backup file."""
    database = setup_sqlite_db
    call_command("dbbackup", database=database, verbosity=0)

    out = io.StringIO()
    call_command("listbackups", stdout=out)

    output = out.getvalue()
    # The backup filename contains the database alias
    assert database in output
    # Should contain the sqlite3 extension
    assert ".sqlite3" in output
