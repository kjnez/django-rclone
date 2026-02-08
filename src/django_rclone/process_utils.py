from __future__ import annotations

import io
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
