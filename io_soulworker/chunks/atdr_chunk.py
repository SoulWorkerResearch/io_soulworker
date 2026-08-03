from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class AtdrChunk_KeyFrame(DataExchange_cl):

    time = 0.0
    angle = 0.0

    def read(self, reader: BinaryReader) -> None:

        self.time = reader.read_float()
        self.angle = reader.read_float()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_float(self.time)
        writer.write_float(self.angle)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "AtdrChunk_KeyFrame":

        value = AtdrChunk_KeyFrame()
        value.read(reader)

        return value


class AtdrChunk(DataExchange_cl):
    """Root-motion rotation track (VisRotationDeltaKeyFrameTrack_cl)."""

    # Vision axis byte: 0 = Z, 1 = Y, 2 = X
    AXIS_Z = 0
    AXIS_Y = 1
    AXIS_X = 2

    version = 1
    axis = AXIS_Y
    key_frame_list: list[AtdrChunk_KeyFrame]

    def __init__(self) -> None:

        self.key_frame_list = []

    def read(self, reader: BinaryReader) -> None:

        self.version = reader.read_uint16()
        assert self.version <= 1

        self.axis = reader.read_uint8()

        count = reader.read_uint32()
        assert count > 0

        frames = [AtdrChunk_KeyFrame.from_reader(reader) for _ in range(count)]

        if self.version == 0:
            previous = 0.0
            for frame in frames:
                absolute = frame.angle
                frame.angle = absolute - previous
                previous = absolute

        self.key_frame_list = frames

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint16(self.version)
        writer.write_uint8(self.axis)
        writer.write_uint32(len(self.key_frame_list))

        if self.version == 0:
            cumulative = 0.0
            for frame in self.key_frame_list:
                cumulative += frame.angle
                writer.write_float(frame.time)
                writer.write_float(cumulative)
        else:
            for frame in self.key_frame_list:
                frame.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "AtdrChunk":

        value = AtdrChunk()
        value.read(reader)

        return value
