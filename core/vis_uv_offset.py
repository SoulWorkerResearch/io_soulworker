from io_soulworker.core.binary_reader import BinaryReader


class VisUVOffset:

    u: int
    v: int

    def __init__(self, reader: BinaryReader) -> None:
        self.u = reader.read_uint8()
        self.v = reader.read_uint8()
