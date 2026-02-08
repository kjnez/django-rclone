from __future__ import annotations

import io
import subprocess
import sys
from unittest.mock import MagicMock

from django_rclone.process_utils import (
    begin_stderr_drain,
    close_process_stdout,
    finish_process,
    join_pipe_drain,
    start_pipe_drain,
)


class _BrokenStream(io.IOBase):
    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        raise OSError("read failed")


class TestProcessUtils:
    def test_start_pipe_drain_returns_none_for_none_stream(self):
        assert start_pipe_drain(None) is None

    def test_start_pipe_drain_returns_none_for_non_io_object(self):
        assert start_pipe_drain(object()) is None  # type: ignore[arg-type]

    def test_start_and_join_pipe_drain_reads_all_bytes(self):
        stream = io.BytesIO(b"abc123")

        drain = start_pipe_drain(stream)

        assert drain is not None
        assert join_pipe_drain(drain) == b"abc123"
        assert stream.closed

    def test_start_pipe_drain_handles_read_and_close_errors(self):
        stream = _BrokenStream()

        drain = start_pipe_drain(stream)  # type: ignore[arg-type]

        assert drain is not None
        assert join_pipe_drain(drain) == b""

    def test_join_pipe_drain_none_returns_empty_bytes(self):
        assert join_pipe_drain(None) == b""

    def test_begin_stderr_drain_detaches_stream(self):
        proc = MagicMock()
        proc.stderr = io.BytesIO(b"stderr")

        drain = begin_stderr_drain(proc)

        assert drain is not None
        assert proc.stderr is None
        assert join_pipe_drain(drain) == b"stderr"

    def test_begin_stderr_drain_returns_none_for_non_io_stream(self):
        proc = MagicMock()
        proc.stderr = MagicMock()

        assert begin_stderr_drain(proc) is None
        assert proc.stderr is not None

    def test_close_process_stdout_closes_and_detaches_stream(self):
        proc = MagicMock()
        stdout_stream = MagicMock()
        proc.stdout = stdout_stream

        close_process_stdout(proc)

        stdout_stream.close.assert_called_once()
        assert proc.stdout is None

    def test_close_process_stdout_noop_when_stdout_is_none(self):
        proc = MagicMock()
        proc.stdout = None

        close_process_stdout(proc)

        assert proc.stdout is None

    def test_finish_process_returns_pipe_output_without_drain(self):
        proc = MagicMock()
        proc.communicate.return_value = (b"stdout", b"stderr")

        stdout, stderr = finish_process(proc)

        assert stdout == b"stdout"
        assert stderr == b"stderr"
        proc.communicate.assert_called_once_with(timeout=None)

    def test_finish_process_prefers_drained_stderr(self):
        proc = MagicMock()
        proc.stderr = io.BytesIO(b"drained")
        proc.communicate.return_value = (b"stdout", b"pipe-stderr")
        drain = begin_stderr_drain(proc)

        stdout, stderr = finish_process(proc, stderr_drain=drain)

        assert stdout == b"stdout"
        assert stderr == b"drained"

    def test_finish_process_can_close_stdout(self):
        proc = MagicMock()
        stdout_stream = MagicMock()
        proc.stdout = stdout_stream
        proc.communicate.return_value = (None, b"stderr")

        stdout, stderr = finish_process(proc, close_stdout=True)

        stdout_stream.close.assert_called_once()
        assert proc.stdout is None
        assert stdout == b""
        assert stderr == b"stderr"

    def test_finish_process_timeout_is_forwarded(self):
        proc = MagicMock()
        proc.communicate.return_value = (b"", b"")

        finish_process(proc, timeout=1.5)

        proc.communicate.assert_called_once_with(timeout=1.5)

    def test_large_stderr_during_streaming_is_drained_without_deadlock(self):
        stderr_size = 262144
        script = (
            "import sys\n"
            "sys.stdout.buffer.write(b'payload')\n"
            "sys.stdout.buffer.flush()\n"
            f"sys.stderr.buffer.write(b'e' * {stderr_size})\n"
            "sys.stderr.buffer.flush()\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        drain = begin_stderr_drain(proc)
        assert proc.stdout is not None

        # Simulates streaming stdout into another consumer before finalizing the process.
        streamed = proc.stdout.read()
        stdout, stderr = finish_process(proc, stderr_drain=drain, close_stdout=True, timeout=5)

        assert proc.returncode == 0
        assert streamed == b"payload"
        assert stdout == b""
        assert len(stderr) == stderr_size
