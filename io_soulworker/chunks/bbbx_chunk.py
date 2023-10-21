from io_soulworker.core.binary_reader import BinaryReader


class BBBXChunk:

    class Entity:

        def __init__(self, reader: BinaryReader):

            self.min = reader.read_float_vector3()
            self.max = reader.read_float_vector3()

    def __init__(self, reader: BinaryReader):

        count = reader.read_uint16()
        self.values = [BBBXChunk.Entity(v) for v in count]
