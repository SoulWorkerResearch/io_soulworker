from io import SEEK_SET
from logging import debug
from traceback import print_exception

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_id import VisChunkId


class VisChunkScope(object):

    cid = VisChunkId.NONE
    depth = 0

    def __init__(self, reader: BinaryReader) -> None:
        self.reader = reader

    def __enter__(self):
        self.depth = self.reader.read_int32()
        debug("enter stack depth: %d", self.depth)

        if self.depth < 0:
            debug("end of file")
            return self

        self.cid = self.reader.read_cid()
        debug("enter chunk id: %s", self.__get_chunk_name(self.cid))

        self.length = self.reader.read_uint32()
        self.pos = self.reader.tell()

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.depth < 0:
            return

        if exc_type is not None:
            print_exception(exc_type, exc_value, traceback)

        offset = self.pos + self.length
        self.reader.seek(offset, SEEK_SET)

        self.depth -= self.reader.read_int32()
        debug("exit stack depth: %d", self.depth)

        exit_cid = self.reader.read_cid()
        debug("exit chunk id: %s", self.__get_chunk_name(exit_cid))

    def __get_chunk_name(self, id: VisChunkId) -> str:
        return id.to_bytes(4, "big").decode("ascii")
