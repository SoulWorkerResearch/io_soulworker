
from io_soulworker.chunks.wght_chunk import WGHTChunk
from io_soulworker.core.binary_reader import BinaryReader


class WGHTChunkReader:

    version = 0

    def __init__(self, reader: BinaryReader) -> None:

        self.__reader__ = reader

        self.version = reader.read_uint32()

    def all_of(self, vertices_count: int) -> list[WGHTChunk]:

        return [WGHTChunk.from_reader(self.__reader__) for _ in range(vertices_count)]

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'WGHTChunkReader':

        return WGHTChunkReader(reader)
