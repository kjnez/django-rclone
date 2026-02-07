from __future__ import annotations

import io
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from django_rclone.exceptions import RcloneError
from django_rclone.rclone import Rclone


class TestRcloneInit:
    def test_defaults_from_settings(self):
        rc = Rclone()
        assert rc.remote == "testremote:backups"
        assert rc.binary == "rclone"
        assert rc.flags == []

    def test_explicit_args(self):
        rc = Rclone(remote="other:path", binary="/usr/bin/rclone", config="/etc/rclone.conf", flags=["--verbose"])
        assert rc.remote == "other:path"
        assert rc.binary == "/usr/bin/rclone"
        assert rc.config == "/etc/rclone.conf"
        assert rc.flags == ["--verbose"]

    @override_settings(DJANGO_RCLONE={"REMOTE": ""})
    def test_remote_is_required(self):
        with pytest.raises(ImproperlyConfigured):
            Rclone()


class TestRemotePath:
    def test_joins_path(self):
        rc = Rclone(remote="myremote:backups")
        assert rc._remote_path("db/file.dump") == "myremote:backups/db/file.dump"

    def test_strips_slashes(self):
        rc = Rclone(remote="myremote:backups/")
        assert rc._remote_path("/db/file.dump") == "myremote:backups/db/file.dump"

    def test_empty_path(self):
        rc = Rclone(remote="myremote:backups")
        assert rc._remote_path("") == "myremote:backups"


class TestBaseCmd:
    def test_without_config(self):
        rc = Rclone(remote="r:b", binary="rclone")
        assert rc._base_cmd() == ["rclone"]

    def test_with_config(self):
        rc = Rclone(remote="r:b", binary="rclone", config="/etc/rclone.conf")
        assert rc._base_cmd() == ["rclone", "--config", "/etc/rclone.conf"]

    def test_with_flags(self):
        rc = Rclone(remote="r:b", binary="rclone", flags=["--verbose", "--stats=1s"])
        assert rc._base_cmd() == ["rclone", "--verbose", "--stats=1s"]


class TestRun:
    @patch("django_rclone.rclone.subprocess.run")
    def test_success(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc._run(["version"])
        mock_run.assert_called_once_with(["rclone", "version"], capture_output=True)

    @patch("django_rclone.rclone.subprocess.run")
    def test_failure_raises(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=b"", stderr=b"something failed"
        )
        rc = Rclone(remote="r:b", binary="rclone")
        with pytest.raises(RcloneError) as exc_info:
            rc._run(["bad-command"])
        assert exc_info.value.returncode == 1
        assert "something failed" in exc_info.value.stderr


class TestRcat:
    @patch("django_rclone.rclone.subprocess.Popen")
    def test_pipes_stdin(self, mock_popen: MagicMock):
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_popen.return_value = proc

        rc = Rclone(remote="r:b", binary="rclone")
        data = io.BytesIO(b"test data")
        rc.rcat("db/backup.dump", stdin=data)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["rclone", "rcat", "r:b/db/backup.dump"]
        assert call_args[1]["stdin"] is data

    @patch("django_rclone.rclone.subprocess.Popen")
    def test_failure_raises(self, mock_popen: MagicMock):
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"upload failed")
        proc.returncode = 1
        mock_popen.return_value = proc

        rc = Rclone(remote="r:b", binary="rclone")
        with pytest.raises(RcloneError):
            rc.rcat("db/backup.dump", stdin=io.BytesIO(b"data"))


class TestCat:
    @patch("django_rclone.rclone.subprocess.Popen")
    def test_returns_popen(self, mock_popen: MagicMock):
        proc = MagicMock()
        mock_popen.return_value = proc

        rc = Rclone(remote="r:b", binary="rclone")
        result = rc.cat("db/backup.dump")
        assert result is proc
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["rclone", "cat", "r:b/db/backup.dump"]


class TestLsjson:
    @patch("django_rclone.rclone.subprocess.run")
    def test_parses_json(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b'[{"Name": "backup.dump", "Size": 1234, "ModTime": "2024-01-15T12:00:00Z"}]',
            stderr=b"",
        )
        rc = Rclone(remote="r:b", binary="rclone")
        result = rc.lsjson("db/")
        assert len(result) == 1
        assert result[0]["Name"] == "backup.dump"

    @patch("django_rclone.rclone.subprocess.run")
    def test_passes_flags(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"[]", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.lsjson("db/", recursive=True)
        cmd = mock_run.call_args[0][0]
        assert "--recursive" in cmd

    @patch("django_rclone.rclone.subprocess.run")
    def test_false_and_none_flags_excluded(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"[]", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.lsjson("db/", recursive=False, max_depth=None)
        cmd = mock_run.call_args[0][0]
        assert cmd == ["rclone", "lsjson", "r:b/db/"]

    @patch("django_rclone.rclone.subprocess.run")
    def test_value_flag(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"[]", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.lsjson("db/", max_depth=2)
        cmd = mock_run.call_args[0][0]
        assert "--max-depth" in cmd
        assert "2" in cmd


class TestSync:
    @patch("django_rclone.rclone.subprocess.run")
    def test_basic_sync(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.sync("/tmp/src", "r:b/dst")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["rclone", "sync", "/tmp/src", "r:b/dst"]

    @patch("django_rclone.rclone.subprocess.run")
    def test_with_flags(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.sync("/tmp/src", "r:b/dst", verbose=True, transfers=4)
        cmd = mock_run.call_args[0][0]
        assert "--verbose" in cmd
        assert "--transfers" in cmd
        assert "4" in cmd

    @patch("django_rclone.rclone.subprocess.run")
    def test_false_and_none_flags_excluded(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.sync("/tmp/src", "r:b/dst", verbose=False, checksum=None)
        cmd = mock_run.call_args[0][0]
        assert cmd == ["rclone", "sync", "/tmp/src", "r:b/dst"]


class TestCopy:
    @patch("django_rclone.rclone.subprocess.run")
    def test_basic_copy(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.copy("/tmp/src", "r:b/dst")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["rclone", "copy", "/tmp/src", "r:b/dst"]

    @patch("django_rclone.rclone.subprocess.run")
    def test_with_boolean_true_flag(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.copy("/tmp/src", "r:b/dst", verbose=True)
        cmd = mock_run.call_args[0][0]
        assert "--verbose" in cmd

    @patch("django_rclone.rclone.subprocess.run")
    def test_with_value_flag(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.copy("/tmp/src", "r:b/dst", transfers=4)
        cmd = mock_run.call_args[0][0]
        assert "--transfers" in cmd
        assert "4" in cmd

    @patch("django_rclone.rclone.subprocess.run")
    def test_false_and_none_flags_excluded(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.copy("/tmp/src", "r:b/dst", verbose=False, checksum=None)
        cmd = mock_run.call_args[0][0]
        assert cmd == ["rclone", "copy", "/tmp/src", "r:b/dst"]

    @patch("django_rclone.rclone.subprocess.run")
    def test_underscore_to_hyphen(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.copy("/tmp/src", "r:b/dst", no_traverse=True)
        cmd = mock_run.call_args[0][0]
        assert "--no-traverse" in cmd


class TestDelete:
    @patch("django_rclone.rclone.subprocess.run")
    def test_deletefile(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.delete("db/old-backup.dump")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["rclone", "deletefile", "r:b/db/old-backup.dump"]


class TestMoveto:
    @patch("django_rclone.rclone.subprocess.run")
    def test_moveto(self, mock_run: MagicMock):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        rc = Rclone(remote="r:b", binary="rclone")
        rc.moveto("db/tmp.dump", "db/final.dump")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["rclone", "moveto", "r:b/db/tmp.dump", "r:b/db/final.dump"]
