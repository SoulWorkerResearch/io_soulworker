from mathutils import Quaternion

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class BrotChunk_KeyFrame(DataExchange_cl):

    bone_count = 0
    time = 0.0
    quaternion_list: list[Quaternion]

    def __init__(self) -> None:

        self.quaternion_list = []

    def read(self, reader: BinaryReader) -> None:

        self.time = reader.read_float()

        self.quaternion_list = [
            reader.read_quaternion() for _ in range(self.bone_count)
        ]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_float(self.time)

        for quat in self.quaternion_list:
            writer.write_quaternion(quat)

    @staticmethod
    def from_reader(reader: BinaryReader, bone_count: int) -> 'BrotChunk_KeyFrame':

        value = BrotChunk_KeyFrame()

        value.bone_count = bone_count
        value.read(reader)

        return value
