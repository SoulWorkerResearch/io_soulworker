from io_soulworker.core.binary_reader import BinaryReader


class WGHTChunk:

    class Entity:

        def __init__(self, reader: BinaryReader):

            # Vertex id ???
            self.vertex = reader.read_uint16()

            # Weight ???
            self.weight = reader.read_uint16() * 0.000015259022

    def __init__(self, reader: BinaryReader):

        count = reader.read_uint16()
        self.values = [WGHTChunk.Entity(reader) for _ in range(count)]
