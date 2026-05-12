from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class St5gChunk(DataExchange_cl):

    version = 0
    f0 = 0.0
    f1 = 0.0
    f2 = 0.0
    f3 = 0.0
    f4 = 0.0
    f5 = 0.0

    def read(self, reader: BinaryReader) -> None:

        self.version = reader.read_uint8()

        self.f0 = reader.read_float()
        self.f1 = reader.read_float()
        self.f2 = reader.read_float()
        self.f3 = reader.read_float()
        self.f4 = reader.read_float()
        self.f5 = reader.read_float()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint8(self.version)

        writer.write_float(self.f0)
        writer.write_float(self.f1)
        writer.write_float(self.f2)
        writer.write_float(self.f3)
        writer.write_float(self.f4)
        writer.write_float(self.f5)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "St5gChunk":

        value = St5gChunk()
        value.read(reader)

        return value
