from __future__ import annotations

import os
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.test.utils import override_settings

from django_rclone.signals import (
    post_db_backup,
    post_db_restore,
    post_media_backup,
    post_media_restore,
    pre_db_backup,
    pre_db_restore,
    pre_media_backup,
    pre_media_restore,
)

from .conftest import requires_rclone, requires_sqlite3

pytestmark = pytest.mark.integration


@requires_sqlite3
@requires_rclone
def test_db_backup_signals_fire(setup_sqlite_db):
    """pre_db_backup and post_db_backup signals fire during a real backup."""
    database = setup_sqlite_db
    received = []

    def on_pre(**kwargs):
        received.append("pre_db_backup")

    def on_post(**kwargs):
        received.append("post_db_backup")

    pre_db_backup.connect(on_pre)
    post_db_backup.connect(on_post)
    try:
        call_command("dbbackup", database=database, verbosity=0)
    finally:
        pre_db_backup.disconnect(on_pre)
        post_db_backup.disconnect(on_post)

    assert "pre_db_backup" in received
    assert "post_db_backup" in received


@requires_sqlite3
@requires_rclone
def test_db_restore_signals_fire(setup_sqlite_db):
    """pre_db_restore and post_db_restore signals fire during a real restore."""
    database = setup_sqlite_db
    call_command("dbbackup", database=database, verbosity=0)

    received = []

    def on_pre(**kwargs):
        received.append("pre_db_restore")

    def on_post(**kwargs):
        received.append("post_db_restore")

    pre_db_restore.connect(on_pre)
    post_db_restore.connect(on_post)
    try:
        db_name = str(settings.DATABASES[database]["NAME"])
        connections[database].close()
        Path(db_name).unlink(missing_ok=True)
        call_command("dbrestore", database=database, interactive=False, verbosity=0)
    finally:
        pre_db_restore.disconnect(on_pre)
        post_db_restore.disconnect(on_post)

    assert "pre_db_restore" in received
    assert "post_db_restore" in received


@requires_rclone
def test_media_backup_signals_fire(tmp_path):
    """pre_media_backup and post_media_backup signals fire during a real media backup."""
    media_root = str(tmp_path / "media")
    rclone_remote = str(tmp_path / "rclone_remote")
    os.makedirs(media_root)

    with open(os.path.join(media_root, "test.txt"), "w") as f:
        f.write("test")

    received = []

    def on_pre(**kwargs):
        received.append("pre_media_backup")

    def on_post(**kwargs):
        received.append("post_media_backup")

    pre_media_backup.connect(on_pre)
    post_media_backup.connect(on_post)
    try:
        with override_settings(MEDIA_ROOT=media_root, DJANGO_RCLONE={"REMOTE": rclone_remote}):
            call_command("mediabackup", verbosity=0)
    finally:
        pre_media_backup.disconnect(on_pre)
        post_media_backup.disconnect(on_post)

    assert "pre_media_backup" in received
    assert "post_media_backup" in received


@requires_rclone
def test_media_restore_signals_fire(tmp_path):
    """pre_media_restore and post_media_restore signals fire during a real media restore."""
    media_root = str(tmp_path / "media")
    rclone_remote = str(tmp_path / "rclone_remote")
    os.makedirs(media_root)

    with open(os.path.join(media_root, "test.txt"), "w") as f:
        f.write("test")

    with override_settings(MEDIA_ROOT=media_root, DJANGO_RCLONE={"REMOTE": rclone_remote}):
        call_command("mediabackup", verbosity=0)

    received = []

    def on_pre(**kwargs):
        received.append("pre_media_restore")

    def on_post(**kwargs):
        received.append("post_media_restore")

    pre_media_restore.connect(on_pre)
    post_media_restore.connect(on_post)
    try:
        with override_settings(MEDIA_ROOT=media_root, DJANGO_RCLONE={"REMOTE": rclone_remote}):
            call_command("mediarestore", verbosity=0)
    finally:
        pre_media_restore.disconnect(on_pre)
        post_media_restore.disconnect(on_post)

    assert "pre_media_restore" in received
    assert "post_media_restore" in received
