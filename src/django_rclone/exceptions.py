class DjangoRcloneError(Exception):
    """Base exception for django-rclone."""


class RcloneError(DjangoRcloneError):
    """Raised when an rclone subprocess fails."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str = ""):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        cmdstr = " ".join(cmd)
        super().__init__(f"rclone command failed (exit {returncode}): {cmdstr}\n{stderr}".strip())


class ConnectorError(DjangoRcloneError):
    """Raised when a database connector fails."""


class ConnectorNotFound(DjangoRcloneError):
    """Raised when no connector is found for a database engine."""

    def __init__(self, engine: str):
        self.engine = engine
        super().__init__(f"No database connector found for engine: {engine}")
