
from logging import debug

from mathutils import Quaternion, Vector

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class VisSkeletalBone_cl(DataExchange_cl):

    PARENT_BONE_INVALID_ID = -1

    id = 0
    name = ""
    parent_id = 0
    inverse_object_space_position = Vector()
    inverse_object_space_orientation = Quaternion()
    local_space_position = Vector()
    local_space_orientation = Quaternion()

    def read(self, reader: BinaryReader) -> None:

        self.name = reader.read_utf8_uint32_string()
        self.parent_id = reader.read_int16()

        self.inverse_object_space_position = reader.read_vector3()
        self.inverse_object_space_orientation = reader.read_quaternion()

        self.local_space_position = reader.read_vector3()
        self.local_space_orientation = reader.read_quaternion()

        debug(f'bone: {self.name}')
        debug(f'parent_id: {self.parent_id}')
        debug('')

    def write(self, writer: BinaryWriter) -> None:

        writer.write_utf8_uint32_string(self.name)
        writer.write_int16(self.parent_id)

        writer.write_vector3(self.inverse_object_space_position)
        writer.write_quaternion(self.inverse_object_space_orientation)

        writer.write_vector3(self.local_space_position)
        writer.write_quaternion(self.local_space_orientation)

    @staticmethod
    def from_reader(reader: BinaryReader, index: int) -> 'VisSkeletalBone_cl':

        value = VisSkeletalBone_cl()

        value.id = index
        value.read(reader)

        return value


class VisSkeletonChunk_cl(DataExchange_cl):

    VERSION = 0

    version = 0
    bones: list['VisSkeletalBone_cl']
    bone_mask_count = 0

    def __init__(self) -> None:

        self.bones = []

    def read(self, reader: BinaryReader) -> None:

        self.version = reader.read_uint16()
        assert self.version == self.VERSION

        bone_count = reader.read_uint16()

        self.bones = [
            VisSkeletalBone_cl.from_reader(reader, index)
            for index in range(bone_count)
        ]

        self.bone_mask_count = reader.read_int16()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint16(self.version)
        writer.write_uint16(len(self.bones))

        for bone in self.bones:

            bone.write(writer)

        writer.write_int16(self.bone_mask_count)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'VisSkeletonChunk_cl':

        value = VisSkeletonChunk_cl()
        value.read(reader)

        return value
