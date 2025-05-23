from io import SEEK_SET
from logging import debug
from traceback import print_exception
from types import TracebackType
from typing import Optional, Type

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_id import VisChunkId


class VisChunkReaderScope(object):

    chunk = VisChunkId.NONE
    depth = 0

    def __init__(self, reader: BinaryReader) -> None:
        self.reader = reader

    def __enter__(self):
        self.depth = self.reader.read_int32()
        debug("enter stack depth: %d", self.depth)

        if self.depth < 0:
            debug("end of file")
            return self

        self.chunk = self.reader.read_cid()
        debug("enter chunk id: %s", self.__get_chunk_name(self.chunk))

        self.length = self.reader.read_uint32()
        self.offset = self.reader.tell()

        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> bool:

        if self.depth < 0:
            return True

        if exc_type is not None:
            print_exception(exc_type, exc_value, traceback)

        offset = self.offset + self.length
        self.reader.seek(offset, SEEK_SET)

        self.depth -= self.reader.read_int32()
        debug("exit stack depth: %d", self.depth)

        exit_cid = self.reader.read_cid()
        debug("exit chunk id: %s", self.__get_chunk_name(exit_cid))

        return False

    def __get_chunk_name(self, id: VisChunkId) -> str:
        return id.to_bytes(4, "big").decode("ascii")
