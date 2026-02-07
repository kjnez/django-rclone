from __future__ import annotations

import os
import subprocess
from typing import Any

from ..exceptions import ConnectorError
from .base import BaseConnector


class PgDumpConnector(BaseConnector):
    """PostgreSQL connector using pg_dump/pg_restore with custom format."""

    @property
    def extension(self) -> str:
        return "dump"

    def _env(self) -> dict[str, str]:
        """Build environment with PGPASSWORD set (never passed via CLI args)."""
        env = os.environ.copy()
        if self.password:
            env["PGPASSWORD"] = self.password
        return env

    def _common_args(self) -> list[str]:
        args: list[str] = []
        if self.host:
            args += ["-h", self.host]
        if self.port:
            args += ["-p", self.port]
        if self.user:
            args += ["-U", self.user]
        return args

    def dump(self) -> subprocess.Popen[bytes]:
        """Dump PostgreSQL database using pg_dump in custom format."""
        cmd = ["pg_dump", "--format=custom", *self._common_args(), self.name]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env(),
        )

    def restore(self, stdin: Any) -> subprocess.Popen[bytes]:
        """Restore PostgreSQL database using pg_restore."""
        cmd = ["pg_restore", "--no-owner", "--no-acl", "-d", self.name, *self._common_args()]
        return subprocess.Popen(
            cmd,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env(),
        )


class PgDumpGisConnector(PgDumpConnector):
    """PostGIS-aware PostgreSQL connector.

    Same as PgDumpConnector, but ensures the PostGIS extension is enabled
    before restore. Requires the ``ADMIN_USER`` key in the database settings
    (used to run the ``CREATE EXTENSION`` command with sufficient privileges).
    """

    def _enable_postgis(self) -> subprocess.CompletedProcess[bytes]:
        """Create PostGIS extension if it doesn't exist."""
        admin_user = self.settings.get("ADMIN_USER", "")
        cmd = [
            "psql",
            "-c",
            "CREATE EXTENSION IF NOT EXISTS postgis;",
            "--no-password",
        ]
        if admin_user:
            cmd += ["-U", admin_user]
        if self.host:
            cmd += ["-h", self.host]
        if self.port:
            cmd += ["-p", self.port]
        cmd.append(self.name)
        return subprocess.run(cmd, capture_output=True, env=self._env())

    def restore(self, stdin: Any) -> subprocess.Popen[bytes]:
        """Enable PostGIS extension, then restore."""
        if self.settings.get("ADMIN_USER"):
            result = self._enable_postgis()
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace").strip()
                raise ConnectorError(f"Failed to enable PostGIS extension: {stderr}")
        return super().restore(stdin)
