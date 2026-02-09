from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_rclone.exceptions import ConnectorError, RcloneError
from django_rclone.signals import post_db_backup, pre_db_backup


class TestDbbackupCommand:
    def _mock_successful_connector(self, mock_get_connector: MagicMock) -> MagicMock:
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 0
        dump_proc.communicate.return_value = (None, b"")
        connector.dump.return_value = dump_proc
        mock_get_connector.return_value = connector
        return connector

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_save_new_backup(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = self._mock_successful_connector(mock_get_connector)
        rclone = MagicMock()
        mock_rclone_cls.return_value = rclone

        call_command("dbbackup", verbosity=0)

        mock_get_connector.assert_called_once_with("default")
        connector.dump.assert_called_once()
        rclone.rcat.assert_called_once()
        rclone.moveto.assert_called_once()

        staged_path = rclone.rcat.call_args[0][0]
        final_path = rclone.moveto.call_args[0][1]
        assert staged_path.startswith("db/default-")
        assert ".sqlite3.partial-" in staged_path
        assert final_path.startswith("db/default-")
        assert final_path.endswith(".sqlite3")
        assert rclone.moveto.call_args[0][0] == staged_path

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_pre_post_signals(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        self._mock_successful_connector(mock_get_connector)
        mock_rclone_cls.return_value = MagicMock()

        received: list[str] = []

        def pre_handler(sender, **kwargs):
            received.append("pre")

        def post_handler(sender, **kwargs):
            received.append("post")

        pre_db_backup.connect(pre_handler, dispatch_uid="dbbackup_pre")
        post_db_backup.connect(post_handler, dispatch_uid="dbbackup_post")
        try:
            call_command("dbbackup", verbosity=0)
            assert received == ["pre", "post"]
        finally:
            pre_db_backup.disconnect(dispatch_uid="dbbackup_pre")
            post_db_backup.disconnect(dispatch_uid="dbbackup_post")

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_cleanup_keeps_latest(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        self._mock_successful_connector(mock_get_connector)
        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Name": f"default-2024-01-{i:02d}-120000.sqlite3", "ModTime": f"2024-01-{i:02d}T12:00:00Z", "Size": 100}
            for i in range(1, 13)
        ]
        mock_rclone_cls.return_value = rclone

        call_command("dbbackup", clean=True, verbosity=0)

        assert rclone.delete.call_count == 2

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_dump_failure_deletes_staged_file(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.extension = "sqlite3"
        dump_proc = MagicMock()
        dump_proc.stdout = MagicMock()
        dump_proc.returncode = 1
        dump_proc.communicate.return_value = (None, b"dump failed")
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
    def test_upload_failure_deletes_staged_file(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        self._mock_successful_connector(mock_get_connector)

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
    def test_finalize_failure_deletes_staged_file(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        self._mock_successful_connector(mock_get_connector)

        rclone = MagicMock()
        rclone.moveto.side_effect = RcloneError(["rclone", "moveto"], 1, "moveto failed")
        mock_rclone_cls.return_value = rclone

        with pytest.raises(SystemExit):
            call_command("dbbackup", verbosity=0)

        rclone.delete.assert_called_once()

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_verbose_output(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        self._mock_successful_connector(mock_get_connector)
        mock_rclone_cls.return_value = MagicMock()

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
    def test_unknown_template_placeholder(
        self,
        mock_get_connector: MagicMock,
        mock_rclone_cls: MagicMock,
        mock_validate: MagicMock,
    ):
        connector = MagicMock()
        connector.extension = "sqlite3"
        mock_get_connector.return_value = connector
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(CommandError, match="unknown placeholder"):
            call_command("dbbackup", verbosity=0)

    @patch("django_rclone.management.commands.dbbackup.validate_db_filename_template")
    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    @override_settings(
        DJANGO_RCLONE={"REMOTE": "testremote:backups", "DB_FILENAME_TEMPLATE": "{database}/{datetime}.{ext}"}
    )
    def test_template_cannot_render_path(
        self,
        mock_get_connector: MagicMock,
        mock_rclone_cls: MagicMock,
        mock_validate: MagicMock,
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
        self._mock_successful_connector(mock_get_connector)
        rclone = MagicMock()
        rclone.lsjson.return_value = [
            {"Name": f"default-2024-01-{i:02d}-120000.sqlite3", "ModTime": f"2024-01-{i:02d}T12:00:00Z", "Size": 100}
            for i in range(1, 13)
        ]
        mock_rclone_cls.return_value = rclone

        out = StringIO()
        call_command("dbbackup", clean=True, verbosity=1, stdout=out)

        assert "Removing old backup" in out.getvalue()

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_uses_finish_process_not_wait(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = self._mock_successful_connector(mock_get_connector)
        mock_rclone_cls.return_value = MagicMock()

        call_command("dbbackup", verbosity=0)

        dump_proc = connector.dump.return_value
        dump_proc.communicate.assert_called_once()
        dump_proc.wait.assert_not_called()

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_uses_central_process_finalizer(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = self._mock_successful_connector(mock_get_connector)
        mock_rclone_cls.return_value = MagicMock()
        drain = (MagicMock(), [b"stderr data"])

        with (
            patch("django_rclone.management.commands.dbbackup.begin_stderr_drain", return_value=drain),
            patch(
                "django_rclone.management.commands.dbbackup.finish_process",
                return_value=(b"", b"stderr data"),
            ) as mock_finish,
        ):
            call_command("dbbackup", verbosity=0)

        mock_finish.assert_called_once_with(connector.dump.return_value, stderr_drain=drain, close_stdout=True)

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_rejects_unknown_database_alias(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(CommandError, match="not configured"):
            call_command("dbbackup", database="missing", verbosity=0)

        mock_get_connector.assert_not_called()

    @patch("django_rclone.management.commands.dbbackup.Rclone")
    @patch("django_rclone.management.commands.dbbackup.get_connector")
    def test_dump_connector_error_exits(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector = MagicMock()
        connector.dump.side_effect = ConnectorError("pg_dump not found")
        connector.extension = "dump"
        mock_get_connector.return_value = connector
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(SystemExit):
            call_command("dbbackup", verbosity=0)

    def test_parse_modtime_invalid_falls_back_to_min(self):
        from django_rclone.management.commands.dbbackup import Command

        parsed = Command._parse_modtime("not-a-timestamp")
        assert parsed.year == 1

    def test_parse_modtime_naive_assumes_utc(self):
        from django_rclone.management.commands.dbbackup import Command

        parsed = Command._parse_modtime("2024-01-01T12:00:00")
        assert parsed.tzinfo is not None
