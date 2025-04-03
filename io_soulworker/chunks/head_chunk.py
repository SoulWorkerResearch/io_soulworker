
from io_soulworker.core.binary_reader import BinaryReader


class HeadChunk:

    def __init__(self, reader: BinaryReader) -> None:

        self.sequence_count = reader.read_uint32()
