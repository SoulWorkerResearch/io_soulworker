from mathutils import Vector

from io_soulworker.chunks.atdo_chunk import AtdoChunk, AtdoChunk_KeyFrame
from io_soulworker.chunks.atdr_chunk import AtdrChunk, AtdrChunk_KeyFrame
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class AtdmChunk(DataExchange_cl):
    """Combined root-motion track (offset + rotation) chunk."""

    keyframe_count = 0
    offset = AtdoChunk()
    rotation = AtdrChunk()

    def __init__(self) -> None:

        self.offset = AtdoChunk()
        self.offset.version = 1
        self.rotation = AtdrChunk()
        self.rotation.version = 1

    def read(self, reader: BinaryReader) -> None:

        self.keyframe_count = reader.read_uint32()
        assert self.keyframe_count > 0

        offset_frames: list[AtdoChunk_KeyFrame] = []
        rotation_frames: list[AtdrChunk_KeyFrame] = []

        previous_offset = Vector((0.0, 0.0, 0.0))
        previous_rotation = Vector((0.0, 0.0, 0.0))
        axis = AtdrChunk.AXIS_Y
        angle = 0.0

        for _ in range(self.keyframe_count):
            time = reader.read_float()
            absolute_offset = reader.read_vector3()
            absolute_rotation = reader.read_vector3()

            offset_frame = AtdoChunk_KeyFrame()
            offset_frame.time = time
            offset_frame.offset = absolute_offset - previous_offset
            offset_frames.append(offset_frame)
            previous_offset = absolute_offset

            rotation_frame = AtdrChunk_KeyFrame()
            rotation_frame.time = time

            if absolute_rotation.x != 0.0:
                axis = AtdrChunk.AXIS_X
                angle = absolute_rotation.x - previous_rotation.x
            elif absolute_rotation.y != 0.0:
                axis = AtdrChunk.AXIS_Y
                angle = absolute_rotation.y - previous_rotation.y
            elif absolute_rotation.z != 0.0:
                axis = AtdrChunk.AXIS_Z
                angle = absolute_rotation.z - previous_rotation.z
            else:
                angle = 0.0

            rotation_frame.angle = angle
            rotation_frames.append(rotation_frame)
            previous_rotation = absolute_rotation

        self.offset.key_frame_list = offset_frames
        self.rotation.axis = axis
        self.rotation.key_frame_list = rotation_frames

    def write(self, writer: BinaryWriter) -> None:

        count = len(self.offset.key_frame_list)
        writer.write_uint32(count)

        cumulative_offset = Vector((0.0, 0.0, 0.0))
        cumulative_angle = 0.0
        axis = self.rotation.axis

        for index in range(count):
            offset_frame = self.offset.key_frame_list[index]
            rotation_frame = self.rotation.key_frame_list[index]

            cumulative_offset = cumulative_offset + offset_frame.offset
            cumulative_angle += rotation_frame.angle

            rotation = Vector((0.0, 0.0, 0.0))
            if axis == AtdrChunk.AXIS_X:
                rotation.x = cumulative_angle
            elif axis == AtdrChunk.AXIS_Y:
                rotation.y = cumulative_angle
            else:
                rotation.z = cumulative_angle

            writer.write_float(offset_frame.time)
            writer.write_vector3(cumulative_offset)
            writer.write_vector3(rotation)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "AtdmChunk":

        value = AtdmChunk()
        value.read(reader)

        return value
