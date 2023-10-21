from io_soulworker.chunks.wght_chunk import WGHTChunk
from io_soulworker.core.binary_reader import BinaryReader


class WGHTChunkReader:

    def all(self, count: int) -> list[WGHTChunk]:

        return [WGHTChunk(self.reader) for _ in count]

    def __init__(self, reader: BinaryReader):

        self.reader = reader
