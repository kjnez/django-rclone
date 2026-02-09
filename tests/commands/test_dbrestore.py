from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_rclone.signals import post_db_restore, pre_db_restore


class TestDbrestoreCommand:
    def _setup_success(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock) -> tuple[MagicMock, MagicMock]:
        connector = MagicMock()
        restore_proc = MagicMock()
        restore_proc.returncode = 0
        restore_proc.communicate.return_value = (None, b"")
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        cat_proc.communicate.return_value = (None, b"")
        rclone.cat.return_value = cat_proc
        mock_rclone_cls.return_value = rclone
        return connector, rclone

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_restore_latest(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector, rclone = self._setup_success(mock_get_connector, mock_rclone_cls)
        rclone.lsjson.return_value = [
            {"Name": "default-2024-01-14-120000.sqlite3", "ModTime": "2024-01-14T12:00:00Z"},
            {"Name": "default-2024-01-15-120000.sqlite3", "ModTime": "2024-01-15T12:00:00Z"},
        ]

        call_command("dbrestore", verbosity=0, interactive=False)

        rclone.cat.assert_called_once_with("db/default-2024-01-15-120000.sqlite3")
        connector.restore.assert_called_once()

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_restore_specific_input_path(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        _, rclone = self._setup_success(mock_get_connector, mock_rclone_cls)

        call_command("dbrestore", input_path="default-2024-01-14-120000.sqlite3", verbosity=0, interactive=False)

        rclone.cat.assert_called_once_with("db/default-2024-01-14-120000.sqlite3")

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_pre_post_signals(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        self._setup_success(mock_get_connector, mock_rclone_cls)

        received: list[str] = []

        def pre_handler(sender, **kwargs):
            received.append("pre")

        def post_handler(sender, **kwargs):
            received.append("post")

        pre_db_restore.connect(pre_handler, dispatch_uid="dbrestore_pre")
        post_db_restore.connect(post_handler, dispatch_uid="dbrestore_post")
        try:
            call_command("dbrestore", input_path="backup.sqlite3", verbosity=0, interactive=False)
            assert received == ["pre", "post"]
        finally:
            pre_db_restore.disconnect(dispatch_uid="dbrestore_pre")
            post_db_restore.disconnect(dispatch_uid="dbrestore_post")

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_cancelled_interactive_restore(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        rclone = MagicMock()
        mock_rclone_cls.return_value = rclone

        with patch("builtins.input", return_value="n"), pytest.raises(SystemExit) as exc_info:
            call_command("dbrestore", input_path="default-2024-01-14-120000.sqlite3", verbosity=0)

        assert exc_info.value.code == 0
        rclone.cat.assert_not_called()

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_explicit_database(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        self._setup_success(mock_get_connector, mock_rclone_cls)

        call_command("dbrestore", database="default", input_path="backup.sqlite3", verbosity=0, interactive=False)

        mock_get_connector.assert_called_once_with("default")

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_interactive_confirm_yes(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector, _ = self._setup_success(mock_get_connector, mock_rclone_cls)

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
    @pytest.mark.filterwarnings("ignore:Overriding setting DATABASES can lead to unexpected behavior\\.:UserWarning")
    def test_requires_database_with_multidb(self):
        with pytest.raises(CommandError):
            call_command("dbrestore", interactive=False, verbosity=0)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_verbose_output(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        self._setup_success(mock_get_connector, mock_rclone_cls)

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
        restore_proc.communicate.return_value = (None, b"")
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 1
        cat_proc.communicate.return_value = (None, b"cat failed")
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
        restore_proc.communicate.return_value = (None, b"restore failed")
        connector.restore.return_value = restore_proc
        mock_get_connector.return_value = connector

        rclone = MagicMock()
        cat_proc = MagicMock()
        cat_proc.stdout = MagicMock()
        cat_proc.returncode = 0
        cat_proc.communicate.return_value = (None, b"")
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

        command = Command()
        with pytest.raises(CommandError, match="cannot be empty"):
            command._validate_input_path("")

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_rejects_backslash_path(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(CommandError, match="relative POSIX-style path"):
            call_command("dbrestore", input_path="sub\\backup.sqlite3", interactive=False, verbosity=0)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_rejects_absolute_path(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(CommandError, match="relative POSIX-style path"):
            call_command("dbrestore", input_path="/absolute/backup.sqlite3", interactive=False, verbosity=0)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_rejects_dot_segment(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        mock_get_connector.return_value = MagicMock()
        mock_rclone_cls.return_value = MagicMock()

        with pytest.raises(CommandError, match="cannot contain '\\.' or '\\.\\.'"):
            call_command("dbrestore", input_path="./backup.sqlite3", interactive=False, verbosity=0)

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_uses_finish_process_not_wait(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector, rclone = self._setup_success(mock_get_connector, mock_rclone_cls)

        call_command("dbrestore", input_path="backup.sqlite3", verbosity=0, interactive=False)

        restore_proc = connector.restore.return_value
        cat_proc = rclone.cat.return_value
        restore_proc.communicate.assert_called_once()
        restore_proc.wait.assert_not_called()
        cat_proc.communicate.assert_called_once()
        cat_proc.wait.assert_not_called()

    @patch("django_rclone.management.commands.dbrestore.Rclone")
    @patch("django_rclone.management.commands.dbrestore.get_connector")
    def test_uses_central_process_finalizer(self, mock_get_connector: MagicMock, mock_rclone_cls: MagicMock):
        connector, rclone = self._setup_success(mock_get_connector, mock_rclone_cls)
        cat_proc = rclone.cat.return_value
        cat_proc.stderr = MagicMock()
        drain = (MagicMock(), [b"stderr data"])

        with (
            patch("django_rclone.management.commands.dbrestore.begin_stderr_drain", return_value=drain),
            patch("django_rclone.management.commands.dbrestore.close_process_stdout") as mock_close_stdout,
            patch(
                "django_rclone.management.commands.dbrestore.finish_process",
                side_effect=[(b"", b""), (b"", b"stderr data")],
            ) as mock_finish,
        ):
            call_command("dbrestore", input_path="backup.sqlite3", verbosity=0, interactive=False)

        mock_close_stdout.assert_called_once_with(cat_proc)
        assert mock_finish.call_count == 2
        mock_finish.assert_any_call(connector.restore.return_value)
        mock_finish.assert_any_call(cat_proc, stderr_drain=drain)
