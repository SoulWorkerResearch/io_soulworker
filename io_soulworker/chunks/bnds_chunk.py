from io_soulworker.core.binary_reader import BinaryReader


class BNDSChunk:

    def __init__(self, reader: BinaryReader):

        self.bounding_box = reader.read_bounding_box()

        self.bounding_sphere_radius = reader.read_float_vector4()

        self.collision_bounding_box = reader.read_bounding_box()
