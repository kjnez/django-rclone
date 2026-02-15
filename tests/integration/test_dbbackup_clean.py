from __future__ import annotations

import io
import time

import pytest
from django.core.management import call_command
from django.test.utils import override_settings

from .conftest import requires_rclone, requires_sqlite3

pytestmark = pytest.mark.integration


@requires_sqlite3
@requires_rclone
def test_dbbackup_clean_removes_old(setup_sqlite_db):
    """Running dbbackup --clean with DB_CLEANUP_KEEP=2 should keep only 2 backups."""
    database = setup_sqlite_db

    # Create 3 backups with small sleeps to ensure different timestamps
    for _ in range(3):
        call_command("dbbackup", database=database, verbosity=0)
        time.sleep(1.1)

    # Verify we have 3 backups
    out = io.StringIO()
    call_command("listbackups", stdout=out)
    output = out.getvalue()
    backup_lines = [line for line in output.strip().split("\n") if ".sqlite3" in line]
    assert len(backup_lines) == 3

    # Run backup with --clean and keep=2
    from django.conf import settings

    rclone_settings = dict(settings.DJANGO_RCLONE)
    rclone_settings["DB_CLEANUP_KEEP"] = 2
    with override_settings(DJANGO_RCLONE=rclone_settings):
        call_command("dbbackup", "--clean", database=database, verbosity=0)

    # Now we should have 2 backups (the new one + 1 old one, oldest deleted)
    out = io.StringIO()
    call_command("listbackups", stdout=out)
    output = out.getvalue()
    backup_lines = [line for line in output.strip().split("\n") if ".sqlite3" in line]
    assert len(backup_lines) == 2
