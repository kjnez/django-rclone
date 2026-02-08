from __future__ import annotations

import io

from django_rclone.process_utils import join_pipe_drain, start_pipe_drain


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
