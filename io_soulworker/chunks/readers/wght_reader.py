
from io_soulworker.chunks.wght_chunk import WGHTChunk
from io_soulworker.core.binary_reader import BinaryReader


class WGHTChunkReader:

    def all_of(self, vertices_count: int) -> list[WGHTChunk]:

        return [WGHTChunk(self.__reader__) for _ in range(vertices_count)]

    def __init__(self, reader: BinaryReader):

        self.__reader__ = reader

        self.u1 = reader.read_uint32()
