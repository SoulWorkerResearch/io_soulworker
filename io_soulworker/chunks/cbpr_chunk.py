from io_soulworker.core.binary_reader import BinaryReader


class CBPRChunk:

    def __init__(self, reader: BinaryReader):

        count = reader.read_uint16()
        self.values = [reader.read_utf8_uint32_string() for _ in count]
