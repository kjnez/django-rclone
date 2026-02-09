from __future__ import annotations

import json
import subprocess
from typing import IO, Any

from django.core.exceptions import ImproperlyConfigured

from .exceptions import RcloneError
from .settings import get_setting


class Rclone:
    """Thin subprocess wrapper around the rclone binary."""

    def __init__(
        self,
        remote: str | None = None,
        config: str | None = None,
        binary: str | None = None,
        flags: list[str] | None = None,
    ):
        self.remote = remote or str(get_setting("REMOTE"))
        if not self.remote:
            raise ImproperlyConfigured("DJANGO_RCLONE['REMOTE'] must be configured.")
        self.config = config or str(get_setting("RCLONE_CONFIG") or "")
        self.binary = binary or str(get_setting("RCLONE_BINARY"))
        self.flags = flags if flags is not None else list(get_setting("RCLONE_FLAGS"))  # type: ignore[arg-type]

    def _base_cmd(self) -> list[str]:
        cmd = [self.binary]
        if self.config:
            cmd += ["--config", self.config]
        cmd += self.flags
        return cmd

    def _run(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        cmd = self._base_cmd() + args
        try:
            result = subprocess.run(cmd, capture_output=True, **kwargs)
        except OSError as exc:
            raise self._command_error(cmd, exc) from exc
        if result.returncode != 0:
            raise RcloneError(cmd, result.returncode, result.stderr.decode(errors="replace"))
        return result

    def _remote_path(self, path: str) -> str:
        """Join the configured remote with a subpath."""
        remote = self.remote.rstrip("/")
        path = path.lstrip("/")
        if path:
            return f"{remote}/{path}"
        return remote

    def rcat(self, path: str, stdin: IO[bytes]) -> None:
        """Pipe data from stdin to a remote file via `rclone rcat`."""
        cmd = [*self._base_cmd(), "rcat", self._remote_path(path)]
        try:
            proc = subprocess.Popen(cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exc:
            raise self._command_error(cmd, exc) from exc
        _, stderr = proc.communicate()
        if proc.returncode != 0:
            raise RcloneError(cmd, proc.returncode, stderr.decode(errors="replace"))

    def cat(self, path: str) -> subprocess.Popen[bytes]:
        """Stream data from a remote file via `rclone cat`. Returns a Popen with stdout."""
        cmd = [*self._base_cmd(), "cat", self._remote_path(path)]
        try:
            return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exc:
            raise self._command_error(cmd, exc) from exc

    def sync(self, src: str, dst: str, **flags: Any) -> None:
        """Sync source to destination directory."""
        args = ["sync", src, dst]
        for key, value in flags.items():
            flag = f"--{key.replace('_', '-')}"
            if value is True:
                args.append(flag)
            elif value is not False and value is not None:
                args += [flag, str(value)]
        self._run(args)

    def copy(self, src: str, dst: str, **flags: Any) -> None:
        """Copy files from source to destination."""
        args = ["copy", src, dst]
        for key, value in flags.items():
            flag = f"--{key.replace('_', '-')}"
            if value is True:
                args.append(flag)
            elif value is not False and value is not None:
                args += [flag, str(value)]
        self._run(args)

    def lsjson(self, path: str = "", **flags: Any) -> list[dict[str, Any]]:
        """List files as JSON at the given remote path."""
        args = ["lsjson", self._remote_path(path)]
        for key, value in flags.items():
            flag = f"--{key.replace('_', '-')}"
            if value is True:
                args.append(flag)
            elif value is not False and value is not None:
                args += [flag, str(value)]
        result = self._run(args)
        return json.loads(result.stdout)

    def delete(self, path: str) -> None:
        """Delete a single remote file via `rclone deletefile`."""
        self._run(["deletefile", self._remote_path(path)])

    def moveto(self, src: str, dst: str) -> None:
        """Move one remote object to another path."""
        self._run(["moveto", self._remote_path(src), self._remote_path(dst)])

    @staticmethod
    def _command_error(cmd: list[str], exc: OSError) -> RcloneError:
        if exc.errno == 2:
            return RcloneError(
                cmd,
                127,
                f"Command not found: {cmd[0]}. Ensure rclone is installed and RCLONE_BINARY is correct.",
            )
        return RcloneError(cmd, 1, str(exc))
