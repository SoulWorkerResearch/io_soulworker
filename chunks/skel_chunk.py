

from io_soulworker.core.binary_reader import BinaryReader


class VisBone(object):
    def __init__(self, reader: BinaryReader) -> None:
        self.name = reader.read_utf8_uint32_string()

        self.parent_id = reader.read_uint16()

        self.inverse_object_space_position = reader.read_float_vector3()
        self.inverse_object_space_orientation = reader.read_quaternion()
        self.local_space_position = reader.read_float_vector3()
        self.local_space_orientation = reader.read_quaternion()


class SkelChunk(object):
    VERSION = 0

    def __init__(self, reader: BinaryReader) -> None:
        self.version = reader.read_uint16()
        assert self.version == self.VERSION

        count = reader.read_uint16()
        self.bones = [VisBone(reader) for _ in range(count)]
