from io_soulworker.core.binary_reader import BinaryReader


class WGHTChunk:

    class Entity:

        def __init__(self, reader: BinaryReader):

            self.u1 = reader.read_uint16()
            self.u2 = reader.read_uint16()

    def __init__(self, reader: BinaryReader):

        count = reader.read_uint16()
        self.values = [WGHTChunk.Entity(reader) for _ in count]
