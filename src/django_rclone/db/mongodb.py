from __future__ import annotations

import subprocess
from typing import Any

from ..exceptions import ConnectorError
from .base import BaseConnector


class MongoDumpConnector(BaseConnector):
    """MongoDB connector using mongodump/mongorestore with archive streaming.

    Uses ``--archive`` flag to stream dump data through stdout/stdin instead of
    writing individual BSON files to disk.
    """

    @property
    def extension(self) -> str:
        return "archive"

    def _host_port(self) -> str:
        host = self.host or "localhost"
        port = self.port or "27017"
        return f"{host}:{port}"

    def _auth_args(self) -> list[str]:
        args: list[str] = []
        if self.user:
            args += ["--username", self.user]
        if self.password:
            args += ["--password", self.password]
        auth_source = self.settings.get("AUTH_SOURCE", "")
        if auth_source:
            args += ["--authenticationDatabase", auth_source]
        return args

    def dump(self) -> subprocess.Popen[bytes]:
        """Dump MongoDB database using mongodump with archive output to stdout."""
        cmd = [
            "mongodump",
            "--db",
            self.name,
            "--host",
            self._host_port(),
            *self._auth_args(),
            "--archive",
        ]
        try:
            return subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise self._command_error("mongodump", exc) from exc

    def restore(self, stdin: Any) -> subprocess.Popen[bytes]:
        """Restore MongoDB database using mongorestore from archive stdin."""
        cmd = [
            "mongorestore",
            "--host",
            self._host_port(),
            *self._auth_args(),
            "--drop",
            "--archive",
        ]
        try:
            return subprocess.Popen(
                cmd,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise self._command_error("mongorestore", exc) from exc

    @staticmethod
    def _command_error(binary: str, exc: OSError) -> ConnectorError:
        if exc.errno == 2:
            return ConnectorError(
                f"Database command '{binary}' not found. Ensure required database client tools are installed."
            )
        return ConnectorError(str(exc))
