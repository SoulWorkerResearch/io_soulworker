from io_soulworker.core.binary_reader import BinaryReader


class BNDSChunk:

    def __init__(self, reader: BinaryReader):

        self.u1_1 = reader.read_float_vector3()
        self.u1_2 = reader.read_float_vector3()

        self.u2 = reader.read_quaternion()

        self.u3_1 = reader.read_float_vector3()
        self.u3_2 = reader.read_float_vector3()
