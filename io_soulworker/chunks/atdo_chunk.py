from mathutils import Vector

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class AtdoChunk_KeyFrame(DataExchange_cl):

    time = 0.0
    offset = Vector((0.0, 0.0, 0.0))

    def read(self, reader: BinaryReader) -> None:

        self.time = reader.read_float()
        self.offset = reader.read_vector3()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_float(self.time)
        writer.write_vector3(self.offset)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "AtdoChunk_KeyFrame":

        value = AtdoChunk_KeyFrame()
        value.read(reader)

        return value


class AtdoChunk(DataExchange_cl):
    """
        Root-motion translation track (VisOffsetDeltaKeyFrameTrack_cl).
        Vision converts version 0 samples to consecutive deltas after load;
        SoulWorker assets use version 1 (absolute offsets).
    """

    version = 1
    key_frame_list: list[AtdoChunk_KeyFrame]

    def __init__(self) -> None:

        self.key_frame_list = []

    def read(self, reader: BinaryReader) -> None:

        self.version = reader.read_uint16()
        assert self.version <= 1

        count = reader.read_uint32()
        assert count > 0

        self.key_frame_list = [
            AtdoChunk_KeyFrame.from_reader(reader) for _ in range(count)
        ]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint16(self.version)
        writer.write_uint32(len(self.key_frame_list))

        for frame in self.key_frame_list:
            frame.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "AtdoChunk":

        value = AtdoChunk()
        value.read(reader)

        return value
