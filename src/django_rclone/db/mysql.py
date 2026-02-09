from __future__ import annotations

import os
import subprocess
from typing import Any

from ..exceptions import ConnectorError
from .base import BaseConnector


class MysqlDumpConnector(BaseConnector):
    """MySQL connector using mysqldump/mysql.

    Security improvement over django-dbbackup: passwords are passed via the
    MYSQL_PWD environment variable, never as command-line arguments.
    """

    @property
    def extension(self) -> str:
        return "sql"

    def _env(self) -> dict[str, str]:
        """Build environment with MYSQL_PWD set (never passed via CLI args)."""
        env = os.environ.copy()
        if self.password:
            env["MYSQL_PWD"] = self.password
        return env

    def _common_args(self) -> list[str]:
        args: list[str] = []
        if self.host:
            args += ["--host", self.host]
        if self.port:
            args += ["--port", self.port]
        if self.user:
            args += ["--user", self.user]
        return args

    def dump(self) -> subprocess.Popen[bytes]:
        """Dump MySQL database using mysqldump."""
        cmd = ["mysqldump", "--quick", *self._common_args(), self.name]
        try:
            return subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env(),
            )
        except OSError as exc:
            raise self._command_error("mysqldump", exc) from exc

    def restore(self, stdin: Any) -> subprocess.Popen[bytes]:
        """Restore MySQL database from stdin."""
        cmd = ["mysql", *self._common_args(), self.name]
        try:
            return subprocess.Popen(
                cmd,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env(),
            )
        except OSError as exc:
            raise self._command_error("mysql", exc) from exc

    @staticmethod
    def _command_error(binary: str, exc: OSError) -> ConnectorError:
        if exc.errno == 2:
            return ConnectorError(
                f"Database command '{binary}' not found. Ensure required database client tools are installed."
            )
        return ConnectorError(str(exc))
