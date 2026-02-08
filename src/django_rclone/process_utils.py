from __future__ import annotations

import io
import subprocess
from contextlib import suppress
from threading import Thread
from typing import IO

PipeDrain = tuple[Thread, list[bytes]] | None


def start_pipe_drain(stream: IO[bytes] | None) -> PipeDrain:
    """Drain a pipe-like stream in the background to avoid pipe-buffer blocking.

    Returns ``None`` when ``stream`` is not a real IO stream (for example a test
    double), so callers can fall back to standard ``communicate()`` behavior.
    """
    if stream is None or not isinstance(stream, io.IOBase):
        return None

    chunks: list[bytes] = []

    def _reader() -> None:
        with suppress(OSError, ValueError):
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        with suppress(OSError, ValueError):
            stream.close()

    thread = Thread(target=_reader, daemon=True)
    thread.start()
    return thread, chunks


def join_pipe_drain(drain: PipeDrain) -> bytes:
    """Join a running drain and return collected bytes."""
    if drain is None:
        return b""
    thread, chunks = drain
    thread.join()
    return b"".join(chunks)


def begin_stderr_drain(proc: subprocess.Popen[bytes]) -> PipeDrain:
    """Start draining ``proc.stderr`` and detach it from communicate() if possible."""
    drain = start_pipe_drain(proc.stderr)
    if drain is not None:
        proc.stderr = None
    return drain


def close_process_stdout(proc: subprocess.Popen[bytes]) -> None:
    """Close and detach ``proc.stdout`` to signal downstream consumers."""
    if proc.stdout is None:
        return
    with suppress(OSError, ValueError):
        proc.stdout.close()
    proc.stdout = None


def finish_process(
    proc: subprocess.Popen[bytes],
    *,
    stderr_drain: PipeDrain = None,
    close_stdout: bool = False,
    timeout: float | None = None,
) -> tuple[bytes, bytes]:
    """Wait for process completion and return ``(stdout, stderr)`` bytes safely."""
    if close_stdout:
        close_process_stdout(proc)
    stdout, stderr_pipe = proc.communicate(timeout=timeout)
    stderr = join_pipe_drain(stderr_drain) or stderr_pipe or b""
    return stdout or b"", stderr
