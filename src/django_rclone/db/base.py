from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Base class for database connectors.

    Reads Django database settings and provides dump/restore as streaming subprocesses.
    """

    def __init__(self, database_settings: dict[str, Any], connector_settings: dict[str, Any] | None = None):
        self.settings = database_settings
        self.connector_settings = connector_settings or {}

    @property
    def name(self) -> str:
        return self.settings.get("NAME", "")

    @property
    def host(self) -> str:
        return self.settings.get("HOST", "")

    @property
    def port(self) -> str:
        return str(self.settings.get("PORT", ""))

    @property
    def user(self) -> str:
        return self.settings.get("USER", "")

    @property
    def password(self) -> str:
        return self.settings.get("PASSWORD", "")

    @property
    @abstractmethod
    def extension(self) -> str:
        """File extension for backups (e.g., 'dump', 'sql', 'sqlite3')."""

    @abstractmethod
    def dump(self) -> subprocess.Popen[bytes]:
        """Start a dump process. Returns a Popen with stdout pipe."""

    @abstractmethod
    def restore(self, stdin: Any) -> subprocess.Popen[bytes]:
        """Start a restore process. Returns a Popen with stdin pipe."""
