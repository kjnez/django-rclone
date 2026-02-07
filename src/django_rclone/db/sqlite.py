from __future__ import annotations

import subprocess
from typing import Any

from .base import BaseConnector


class SqliteConnector(BaseConnector):
    """SQLite database connector using the sqlite3 .backup command."""

    @property
    def extension(self) -> str:
        return "sqlite3"

    def dump(self) -> subprocess.Popen[bytes]:
        """Dump SQLite database to stdout using `.dump` command."""
        cmd = ["sqlite3", self.name, ".dump"]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def restore(self, stdin: Any) -> subprocess.Popen[bytes]:
        """Restore SQLite database from stdin."""
        cmd = ["sqlite3", self.name]
        return subprocess.Popen(cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
