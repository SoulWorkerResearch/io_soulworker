from io_soulworker.core.binary_reader import BinaryReader


class VisMeshEffect:
    
    def __init__(self, reader: BinaryReader) -> None:

        self.name = reader.read_utf8_uint32_string()
        self.flags = reader.read_uint32()
