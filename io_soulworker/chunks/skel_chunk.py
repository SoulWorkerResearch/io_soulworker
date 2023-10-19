from io_soulworker.core.binary_reader import BinaryReader
from mathutils import Matrix
from mathutils import Quaternion
import struct
counter = 0
class VisBone(object):
    def __init__(self, reader: BinaryReader) -> None:
        self.name = reader.read_utf8_uint32_string()
        global counter
        self.id = counter
        if counter == 0:
            self.id = 65535 # -1
        counter += 1
        self.parent_id = reader.read_uint16()

        self.inverse_object_space_position = reader.read_float_vector3()
        self.inverse_object_space_orientation = reader.read_quaternion()
        self.local_pos = reader.read_float_vector3()
        self.local_rot = reader.read_float_vector4()
        quat_bytes_w = struct.unpack('<I', struct.pack('<f', self.local_rot[3]))
        quat_bytes_w = quat_bytes_w[0] ^ 0x80000000
        quatWFloat = struct.unpack('<f', struct.pack('<I', quat_bytes_w))
        self.local_rot = Quaternion(((quatWFloat[0], self.local_rot[0], self.local_rot[1], self.local_rot[2])))
        self.local_rot_euler = self.local_rot.to_euler("XYZ")

class SkelChunk(object):
    VERSION = 0

    def __init__(self, reader: BinaryReader) -> None:
        self.version = reader.read_uint16()
        assert self.version == self.VERSION
        global counter
        counter = 0
        count = reader.read_uint16()
        self.bones = [VisBone(reader) for _ in range(count)]