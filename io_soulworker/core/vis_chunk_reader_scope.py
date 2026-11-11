from io import SEEK_SET
from logging import debug
from types import TracebackType
from typing import Optional, Type
from ..core.binary_reader import BinaryReader
from ..core.vis_chunk_id import VisChunkId


CLOSING_MARKER_SIZE = 8
"""Bytes after the data of a chunk: the depth change and the chunk id."""


class VisChunkReaderScope(object):

    chunk = VisChunkId.NONE
    depth = 0

    exit_chunk_id = VisChunkId.NONE

    def __init__(self, reader: BinaryReader) -> None:

        self.reader = reader

    def __enter__(self):

        self.depth = self.reader.read_int32()
        debug("enter stack depth: %d", self.depth)

        if self.depth < 0:

            debug("end of file")
            self.exit_chunk_id = VisChunkId.NONE
            return self

        self.chunk = self.reader.read_cid()
        debug("enter chunk id: %s", VisChunkId.get_name(self.chunk))

        self.length = self.reader.read_uint32()
        self.offset = self.reader.tell()

        # Refuse a chunk that runs past the end of the file before anything
        # is built from it.
        what = "a chunk with an unknown id"

        if self.chunk != VisChunkId.NONE:

            what = f"the {VisChunkId.get_name(self.chunk)} chunk"

        self.reader.ensure_available(self.length + CLOSING_MARKER_SIZE, what)

        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> bool:

        if self.depth < 0:

            # end of file: nothing to skip, and an error must still propagate
            return False

        if exc_type is None:

            self._leave()
            return False

        # The block failed. Still move to the end of the chunk, so a caller
        # that catches the error can read on, but never let a failure here (a
        # cut file has no end to find) replace the error on its way out.
        try:

            self._leave()

        except Exception as exc:

            debug(
                "cannot find the end of chunk %s: %s",
                VisChunkId.get_name(self.chunk),
                exc
            )

        return False

    def _leave(self) -> None:

        offset = self.offset + self.length
        self.reader.seek(offset, SEEK_SET)

        self.depth -= self.reader.read_int32()
        debug("exit stack depth: %d", self.depth)

        self.exit_chunk_id = self.reader.read_cid()

        debug(
            "exit chunk id: %s",
            VisChunkId.get_name(self.exit_chunk_id)
        )
