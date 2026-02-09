from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from django_rclone.signals import post_media_restore, pre_media_restore


class TestMediarestoreCommand:
    @patch("django_rclone.management.commands.mediarestore.Rclone")
    def test_restore_mediafiles(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        call_command("mediarestore", verbosity=0)

        rclone.sync.assert_called_once_with("testremote:backups/media", "/tmp/django_rclone_test_media")

    @patch("django_rclone.management.commands.mediarestore.Rclone")
    @override_settings(MEDIA_ROOT="")
    def test_missing_media_root(self, mock_rclone_cls: MagicMock):
        with pytest.raises(SystemExit):
            call_command("mediarestore", verbosity=0)

    @patch("django_rclone.management.commands.mediarestore.Rclone")
    def test_verbose_output(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        out = StringIO()
        call_command("mediarestore", verbosity=1, stdout=out)

        output = out.getvalue()
        assert "Syncing media from" in output
        assert "Media restore completed" in output

    @patch("django_rclone.management.commands.mediarestore.Rclone")
    def test_pre_post_signals(self, mock_rclone_cls: MagicMock):
        rclone = MagicMock()
        rclone._remote_path.return_value = "testremote:backups/media"
        mock_rclone_cls.return_value = rclone

        received: list[str] = []

        def pre_handler(sender, **kwargs):
            received.append("pre")

        def post_handler(sender, **kwargs):
            received.append("post")

        pre_media_restore.connect(pre_handler, dispatch_uid="mediarestore_pre")
        post_media_restore.connect(post_handler, dispatch_uid="mediarestore_post")
        try:
            call_command("mediarestore", verbosity=0)
            assert received == ["pre", "post"]
        finally:
            pre_media_restore.disconnect(dispatch_uid="mediarestore_pre")
            post_media_restore.disconnect(dispatch_uid="mediarestore_post")
