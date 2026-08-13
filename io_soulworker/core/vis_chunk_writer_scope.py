from io import BytesIO
from types import TracebackType
from typing import Optional, Type

from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.vis_chunk_id import VisChunkId


class VisChunkWriterScope:
    """Write a length-prefixed Vision chunk envelope (enter + payload + exit)."""

    def __init__(
        self,
        writer: BinaryWriter,
        chunk_id: VisChunkId,
        *,
        depth: int = 0,
        exit_adj: int = 0,
    ) -> None:

        self.writer = writer
        self.chunk_id = chunk_id
        self.depth = depth
        self.exit_adj = exit_adj
        self._payload = BytesIO()
        self._payload_writer: BinaryWriter | None = None

    def __enter__(self) -> BinaryWriter:

        self._payload = BytesIO()
        self._payload_writer = BinaryWriter(self._payload)

        return self._payload_writer

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:

        if exc_type is not None:

            return False

        assert self._payload_writer is not None
        self._payload_writer.flush()
        raw = self._payload.getvalue()

        self.writer.write_int32(self.depth)
        self.writer.write_cid(self.chunk_id)
        self.writer.write_uint32(len(raw))
        self.writer.write(raw)
        self.writer.write_int32(self.exit_adj)
        self.writer.write_cid(self.chunk_id)

        return False


def write_chunk_file_eof(writer: BinaryWriter) -> None:

    writer.write_int32(-1)
