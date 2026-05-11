from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl

WGHT_WEIGHT_QUANTUM = 0.000015259022


class WGHTChunk(DataExchange_cl):

    class Entity(DataExchange_cl):

        bone_index = 0
        weight = 0.0

        def read(self, reader: BinaryReader) -> None:

            self.bone_index = reader.read_uint16()
            self.weight = reader.read_uint16() * WGHT_WEIGHT_QUANTUM

        def write(self, writer: BinaryWriter) -> None:

            writer.write_uint16(self.bone_index)
            q = max(0, min(65535, int(round(self.weight / WGHT_WEIGHT_QUANTUM))))
            writer.write_uint16(q)

        @staticmethod
        def from_reader(reader: BinaryReader) -> 'WGHTChunk.Entity':

            value = WGHTChunk.Entity()
            value.read(reader)

            return value

    values: list['WGHTChunk.Entity']

    def __init__(self) -> None:

        self.values = []

    def read(self, reader: BinaryReader) -> None:

        count = reader.read_uint16()
        self.values = [WGHTChunk.Entity.from_reader(reader) for _ in range(count)]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint16(len(self.values))

        for entity in self.values:
            entity.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'WGHTChunk':

        value = WGHTChunk()
        value.read(reader)

        return value
