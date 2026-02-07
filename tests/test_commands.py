from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_rclone.exceptions import RcloneError
from django_rclone.management.commands.listbackups import Command as ListbackupsCommand
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


class TestDbbackupCommand:
    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_basic_backup(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        # Setup connector mock
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 0
        dump_proc.wait.return_value = 0
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector

        # Setup rclone mock
        rclone = MagicMock()
        mock_rclone_cls.return_value = rclone

        call_command("dbbackup", verbosity=0)

        mock_get_connector.assert_called_once_with("default")
        connector.dump.assert_called_once()
        rclone.rcat.assert_called_once()
        rclone.moveto.assert_called_once()
        # Verify a staged upload is used and then finalized to the expected extension.
        rcat_path = rclone.rcat.call_args[0][0]
        assert rcat_path.startswith("db/default-")
        assert ".sqlite3.partial-" in rcat_path
        final_path = rclone.moveto.call_args[0][1]
        assert final_path.startswith("db/default-")
        assert final_path.endswith(".sqlite3")
        assert rclone.moveto.call_args[0][0] == rcat_path

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_sends_signals(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 0
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector
        mock_rclone_cls.return_value = MagicMock()

        signals_received: list[str] = []

        def pre_handler(sender, **kwargs):
            signals_received.append("pre")

        def post_handler(sender, **kwargs):
            signals_received.append("post")

        pre_db_backup.connect(pre_handler, dispatch_uid="test_pre_backup")
        post_db_backup.connect(post_handler, dispatch_uid="test_post_backup")

        try:
            call_command("dbbackup", verbosity=0)
            assert signals_received == ["pre", "post"]
        finally:
            pre_db_backup.disconnect(dispatch_uid="test_pre_backup")
            post_db_backup.disconnect(dispatch_uid="test_post_backup")

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_cleanup(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 0
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        # Return 12 backups, keep=10 means 2 should be deleted
        rclone.lsjson.return_value = [
            {"Name": f"default-2024-01-{i:02d}-120000.sqlite3", "ModTime": f"2024-01-{i:02d}T12:00:00Z", "Size": 100}
            for i in range(1, 13)
        ]
        mock_rclone_cls.return_value = rclone

        call_command("dbbackup", clean=True, verbosity=0)
        assert rclone.delete.call_count == 2

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_dump_failure_deletes_staged_backup(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 1
        dump_proc.stderr.read.return_value = b"dump failed"
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        mock_rclone_cls.return_value = rclone

        with pytest.raises(SystemExit):
            call_command("dbbackup", verbosity=0)

        staged_path = rclone.rcat.call_args[0][0]
        rclone.delete.assert_called_once_with(staged_path)
        rclone.moveto.assert_not_called()

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_upload_failure_deletes_staged_backup(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 0
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        rclone.rcat.side_effect = RcloneError(["rclone", "rcat"], 1, "upload failed")
        mock_rclone_cls.return_value = rclone

        with pytest.raises(SystemExit):
            call_command("dbbackup", verbosity=0)

        staged_path = rclone.rcat.call_args[0][0]
        rclone.delete.assert_called_once_with(staged_path)
        rclone.moveto.assert_not_called()

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_moveto_failure_deletes_staged_backup(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 0
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        rclone.moveto.side_effect = RcloneError(["rclone", "moveto"], 1, "moveto failed")
        mock_rclone_cls.return_value = rclone

        with pytest.raises(SystemExit):
            call_command("dbbackup", verbosity=0)

        rclone.delete.assert_called_once()

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_verbose_output(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 0
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector
        mock_rclone_cls.return_value = MagicMock()

        from io import StringIO

        out = StringIO()
        call_command("dbbackup", verbosity=1, stdout=out)
        output = out.getvalue()
        assert "Backing up database" in output
        assert "Backup completed" in output

    @patch("django_rclone.management.commands.dbbackup.validate_db_filename_template")
    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    @override_settings(
        DJANGO_RCLONE={"REMOTE": "testremote:backups", "DB_FILENAME_TEMPLATE": "{database}-{datetime}-{missing}.{ext}"}
    )
    def test_template_key_error(
        self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock, mock_validate: MagicMock
    ):
        connector = MagicMock()
        connector.extension = "sqlite3"
        mock_get_connector.return_value = connector
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(CommandError, match="unknown placeholder"):
            call_command("dbbackup", verbosity=0)

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    @patch("django_rclone.management.commands.dbbackup.validate_db_filename_template")
    @override_settings(
        DJANGO_RCLONE={
            "REMOTE": "testremote:backups",
            "DB_FILENAME_TEMPLATE": "{database}/{datetime}.{ext}",
        }
    )
    def test_filename_with_slash(
        self, mock_validate: MagicMock, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock
    ):
        connector = MagicMock()
        connector.extension = "sqlite3"
        mock_get_connector.return_value = connector
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(CommandError, match="must render a filename, not a path"):
            call_command("dbbackup", verbosity=0)

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_cleanup_verbose_output(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 0
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Name": f"default-2024-01-{i:02d}-120000.sqlite3", "ModTime": f"2024-01-{i:02d}T12:00:00Z", "Size": 100}
            for i in range(1, 13)
        ]
        mock_rclone_cls.return_value = rclone

        from io import StringIO

        out = StringIO()
        call_command("dbbackup", clean=True, verbosity=1, stdout=out)
        output = out.getvalue()
        assert "Removing old backup" in output


class TestDbestoreCommand:
    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_restore_latest(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 0
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Name": "default-2024-01-14-120000.sqlite3", "ModTime": "2024-01-14T12:00:00Z"},
            {"Name": "default-2024-01-15-120000.sqlite3", "ModTime": "2024-01-15T12:00:00Z"},
        ]
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone

        call_command("dbrestore", verbosity=0, interactive=False)

        # Should pick the latest backup
        rclone.cat.assert_called_once_with("db/default-2024-01-15-120000.sqlite3")
        connector.restore.assert_called_once()

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_restore_specific_path(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 0
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone

        call_command("dbrestore", input_path="default-2024-01-14-120000.sqlite3", verbosity=0, interactive=False)
        rclone.cat.assert_called_once_with("db/default-2024-01-14-120000.sqlite3")

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_sends_signals(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 0
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone

        signals_received: list[str] = []

        def pre_handler(sender, **kwargs):
            signals_received.append("pre")

        def post_handler(sender, **kwargs):
            signals_received.append("post")

        pre_db_restore.connect(pre_handler, dispatch_uid="test_pre_restore")
        post_db_restore.connect(post_handler, dispatch_uid="test_post_restore")

        try:
            call_command("dbrestore", input_path="backup.sqlite3", verbosity=0, interactive=False)
            assert signals_received == ["pre", "post"]
        finally:
            pre_db_restore.disconnect(dispatch_uid="test_pre_restore")
            post_db_restore.disconnect(dispatch_uid="test_post_restore")

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_cancelled_restore_does_not_run(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        mock_get_connector.return_value = connector
        rclone = MagicMock()
        mock_rclone_cls.return_value = rclone

        with patch("builtins.input", return_value="n"), pytest.raises(SystemExit) as exc_info:
            call_command("dbrestore", input_path="default-2024-01-14-120000.sqlite3", verbosity=0)
        assert exc_info.value.code == 0
        rclone.cat.assert_not_called()

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_restore_with_explicit_database(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 0
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone

        call_command("dbrestore", database="default", input_path="backup.sqlite3", verbosity=0, interactive=False)
        mock_get_connector.assert_called_once_with("default")

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_interactive_confirm_yes(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 0
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone

        with patch("builtins.input", return_value="y"):
            call_command("dbrestore", input_path="backup.sqlite3", verbosity=0)
        connector.restore.assert_called_once()

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_rejects_parent_path_segments(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        mock_rclone_cls.return_value = MagicMock()
        with pytest.raises(CommandError):
            call_command("dbrestore", input_path="../backup.sqlite3", interactive=False, verbosity=0)

    @override_settings(
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
            "analytics": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        }
    )
    def test_requires_database_when_multiple_databases(self):
        with pytest.raises(CommandError):
            call_command("dbrestore", interactive=False, verbosity=0)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_verbose_output(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 0
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone

        from io import StringIO

        out = StringIO()
        call_command("dbrestore", input_path="backup.sqlite3", verbosity=1, interactive=False, stdout=out)
        output = out.getvalue()
        assert "Restoring database" in output
        assert "Restore completed" in output

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_cat_process_failure(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 0
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 1
        cat_proc.stderr.read.return_value = b"cat failed"
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone

        with pytest.raises(SystemExit):
            call_command("dbrestore", input_path="backup.sqlite3", verbosity=0, interactive=False)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_restore_process_failure(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 1
        restore_proc.stderr.read.return_value = b"restore failed"
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone

        with pytest.raises(SystemExit):
            call_command("dbrestore", input_path="backup.sqlite3", verbosity=0, interactive=False)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_find_latest_no_backups(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        rclone = MagicMock()
        rclone.lsjson.return_value = []
        mock_rclone_cls.return_value = rclone

        with pytest.raises(SystemExit):
            call_command("dbrestore", verbosity=0, interactive=False)

    def test_validate_input_path_empty(self):
        from django_rclone.management.commands.dbrestore import Command

        cmd = Command()
        with pytest.raises(CommandError, match="cannot be empty"):
            cmd._validate_input_path("")

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_rejects_backslash_in_input_path(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        mock_rclone_cls.return_value = MagicMock()
        with pytest.raises(CommandError, match="relative POSIX-style path"):
            call_command("dbrestore", input_path="sub\\backup.sqlite3", interactive=False, verbosity=0)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_rejects_absolute_input_path(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        mock_rclone_cls.return_value = MagicMock()
        with pytest.raises(CommandError, match="relative POSIX-style path"):
            call_command("dbrestore", input_path="/absolute/backup.sqlite3", interactive=False, verbosity=0)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_rejects_dot_segment_in_input_path(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        mock_rclone_cls.return_value = MagicMock()
        with pytest.raises(CommandError, match="cannot contain '\\.' or '\\.\\.'"):
            call_command("dbrestore", input_path="./backup.sqlite3", interactive=False, verbosity=0)


class TestMediabackupCommand:
    @patch("django_rclone.management.commands.mediabackup.Rclone")
    def test_basic_media_backup(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        call_command("mediabackup", verbosity=0)
        rclone.sync.assert_called_once_with("/tmp/django_rclone_test_media", "testremote:backups/media")

    @patch("django_rclone.management.commands.mediabackup.Rclone")
    @override_settings(MEDIA_ROOT="")
    def test_no_media_root(self, mock_rclone_cls: MagicMock):
        with pytest.raises(SystemExit):
            call_command("mediabackup", verbosity=0)

    @patch("django_rclone.management.commands.mediabackup.Rclone")
    def test_verbose_output(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        from io import StringIO

        out = StringIO()
        call_command("mediabackup", verbosity=1, stdout=out)
        output = out.getvalue()
        assert "Syncing media from" in output
        assert "Media backup completed" in output

    @patch("django_rclone.management.commands.mediabackup.Rclone")
    def test_sends_signals(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        signals_received: list[str] = []

        def pre_handler(sender, **kwargs):
            signals_received.append("pre")

        def post_handler(sender, **kwargs):
            signals_received.append("post")

        pre_media_backup.connect(pre_handler, dispatch_uid="test_pre_media_backup")
        post_media_backup.connect(post_handler, dispatch_uid="test_post_media_backup")

        try:
            call_command("mediabackup", verbosity=0)
            assert signals_received == ["pre", "post"]
        finally:
            pre_media_backup.disconnect(dispatch_uid="test_pre_media_backup")
            post_media_backup.disconnect(dispatch_uid="test_post_media_backup")


class TestMediarestoreCommand:
    @patch("django_rclone.management.commands.mediarestore.Rclone")
    def test_basic_media_restore(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        call_command("mediarestore", verbosity=0)
        rclone.sync.assert_called_once_with("testremote:backups/media", "/tmp/django_rclone_test_media")

    @patch("django_rclone.management.commands.mediarestore.Rclone")
    @override_settings(MEDIA_ROOT="")
    def test_no_media_root(self, mock_rclone_cls: MagicMock):
        with pytest.raises(SystemExit):
            call_command("mediarestore", verbosity=0)

    @patch("django_rclone.management.commands.mediarestore.Rclone")
    def test_verbose_output(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        from io import StringIO

        out = StringIO()
        call_command("mediarestore", verbosity=1, stdout=out)
        output = out.getvalue()
        assert "Syncing media from" in output
        assert "Media restore completed" in output

    @patch("django_rclone.management.commands.mediarestore.Rclone")
    def test_sends_signals(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        signals_received: list[str] = []

        def pre_handler(sender, **kwargs):
            signals_received.append("pre")

        def post_handler(sender, **kwargs):
            signals_received.append("post")

        pre_media_restore.connect(pre_handler, dispatch_uid="test_pre_media_restore")
        post_media_restore.connect(post_handler, dispatch_uid="test_post_media_restore")

        try:
            call_command("mediarestore", verbosity=0)
            assert signals_received == ["pre", "post"]
        finally:
            pre_media_restore.disconnect(dispatch_uid="test_pre_media_restore")
            post_media_restore.disconnect(dispatch_uid="test_post_media_restore")


class TestListbackupsCommand:
    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_list_db_backups(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Name": "default-2024-01-15-120000.sqlite3", "Size": 1024, "ModTime": "2024-01-15T12:00:00Z"},
        ]
        mock_rclone_cls.return_value = rclone

        call_command("listbackups", verbosity=0)
        rclone.lsjson.assert_called_once()

    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_list_media_backups(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Path": "photos/img.jpg", "Name": "img.jpg", "Size": 2048, "ModTime": "2024-01-15T12:00:00Z"},
        ]
        mock_rclone_cls.return_value = rclone

        call_command("listbackups", media=True, verbosity=0)
        rclone.lsjson.assert_called_once()

    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_filter_by_database(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Name": "default-2024-01-15-120000.sqlite3", "Size": 1024, "ModTime": "2024-01-15T12:00:00Z"},
            {"Name": "analytics-2024-01-15-120000.sqlite3", "Size": 512, "ModTime": "2024-01-15T12:00:00Z"},
        ]
        mock_rclone_cls.return_value = rclone

        from io import StringIO

        out = StringIO()
        call_command("listbackups", database="default", stdout=out)
        output = out.getvalue()
        assert "default-2024-01-15-120000.sqlite3" in output
        assert "analytics-2024-01-15-120000.sqlite3" not in output

    @patch("django_rclone.management.commands.listbackups.Rclone")
    @override_settings(
        DJANGO_RCLONE={
            "REMOTE": "testremote:backups",
            "DB_FILENAME_TEMPLATE": "{datetime}-{database}.{ext}",
        }
    )
    def test_invalid_template_is_rejected(self, mock_rclone_cls: MagicMock):
        mock_rclone_cls.return_value = MagicMock()
        with pytest.raises(CommandError):
            call_command("listbackups", database="default")

    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_no_db_backups(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = []
        mock_rclone_cls.return_value = rclone

        from io import StringIO

        out = StringIO()
        call_command("listbackups", stdout=out)
        assert "No database backups found" in out.getvalue()

    @patch("django_rclone.management.commands.listbackups.Rclone")
    def test_no_media_backups(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone.lsjson.return_value = []
        mock_rclone_cls.return_value = rclone

        from io import StringIO

        out = StringIO()
        call_command("listbackups", media=True, stdout=out)
        assert "No media backups found" in out.getvalue()


class TestFormatSize:
    def test_bytes(self):
        assert ListbackupsCommand._format_size(512) == "512 B"

    def test_kilobytes(self):
        assert ListbackupsCommand._format_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert ListbackupsCommand._format_size(1024**2) == "1.0 MB"

    def test_gigabytes(self):
        assert ListbackupsCommand._format_size(1024**3) == "1.0 GB"

    def test_terabytes(self):
        assert ListbackupsCommand._format_size(1024**4) == "1.0 TB"

    def test_petabytes(self):
        assert ListbackupsCommand._format_size(1024**5) == "1.0 PB"
