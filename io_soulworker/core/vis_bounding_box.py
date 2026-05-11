from mathutils import Vector

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class HavokBoundingBox(DataExchange_cl):

    min = Vector()
    max = Vector()

    def read(self, reader: BinaryReader) -> None:

        self.min = reader.read_vector3()
        self.max = reader.read_vector3()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_vector3(self.min)
        writer.write_vector3(self.max)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'HavokBoundingBox':

        value = HavokBoundingBox()
        value.read(reader)

        return value
