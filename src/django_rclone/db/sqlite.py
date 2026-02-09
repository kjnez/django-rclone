from __future__ import annotations

import subprocess
from typing import Any

from ..exceptions import ConnectorError
from .base import BaseConnector


class SqliteConnector(BaseConnector):
    """SQLite database connector using the sqlite3 .backup command."""

    @property
    def extension(self) -> str:
        return "sqlite3"

    def dump(self) -> subprocess.Popen[bytes]:
        """Dump SQLite database to stdout using `.dump` command."""
        cmd = ["sqlite3", self.name, ".dump"]
        try:
            return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exc:
            raise self._command_error("sqlite3", exc) from exc

    def restore(self, stdin: Any) -> subprocess.Popen[bytes]:
        """Restore SQLite database from stdin."""
        cmd = ["sqlite3", self.name]
        try:
            return subprocess.Popen(cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exc:
            raise self._command_error("sqlite3", exc) from exc

    @staticmethod
    def _command_error(binary: str, exc: OSError) -> ConnectorError:
        if exc.errno == 2:
            return ConnectorError(
                f"Database command '{binary}' not found. Ensure required database client tools are installed."
            )
        return ConnectorError(str(exc))
