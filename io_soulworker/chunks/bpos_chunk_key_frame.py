from mathutils import Vector

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class BposChunk_KeyFrame(DataExchange_cl):

    bone_count = 0
    time = 0.0
    vector_list: list[Vector] = []

    def __init__(self) -> None:

        self.vector_list = []

    def read(self, reader: BinaryReader) -> None:

        self.time = reader.read_float()

        self.vector_list = [
            Vector([*(reader.read_float() for _ in range(3)), 1.0]) for _ in range(self.bone_count)
        ]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_float(self.time)

        for vec in self.vector_list:

            writer.write_float(vec.x)
            writer.write_float(vec.y)
            writer.write_float(vec.z)

    @staticmethod
    def from_reader(reader: BinaryReader, bone_count: int) -> 'BposChunk_KeyFrame':

        value = BposChunk_KeyFrame()

        value.bone_count = bone_count
        value.read(reader)

        return value
