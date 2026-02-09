from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from django_rclone.signals import post_media_backup, pre_media_backup


class TestMediabackupCommand:
    @patch("django_rclone.management.commands.mediabackup.Rclone")
    def test_backup_mediafiles(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        call_command("mediabackup", verbosity=0)

        rclone.sync.assert_called_once_with("/tmp/django_rclone_test_media", "testremote:backups/media")

    @patch("django_rclone.management.commands.mediabackup.Rclone")
    @override_settings(MEDIA_ROOT="")
    def test_missing_media_root(self, mock_rclone_cls: MagicMock):
        with pytest.raises(SystemExit):
            call_command("mediabackup", verbosity=0)

    @patch("django_rclone.management.commands.mediabackup.Rclone")
    def test_verbose_output(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        out = StringIO()
        call_command("mediabackup", verbosity=1, stdout=out)

        output = out.getvalue()
        assert "Syncing media from" in output
        assert "Media backup completed" in output

    @patch("django_rclone.management.commands.mediabackup.Rclone")
    def test_pre_post_signals(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        received: list[str] = []

        def pre_handler(sender, **kwargs):
            received.append("pre")

        def post_handler(sender, **kwargs):
            received.append("post")

        pre_media_backup.connect(pre_handler, dispatch_uid="mediabackup_pre")
        post_media_backup.connect(post_handler, dispatch_uid="mediabackup_post")
        try:
            call_command("mediabackup", verbosity=0)
            assert received == ["pre", "post"]
        finally:
            pre_media_backup.disconnect(dispatch_uid="mediabackup_pre")
            post_media_backup.disconnect(dispatch_uid="mediabackup_post")
