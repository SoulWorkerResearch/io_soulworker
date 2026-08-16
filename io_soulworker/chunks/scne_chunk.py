from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


SCNE_MAGIC = 220878


class ScneChunk(DataExchange_cl):
    """Scene document header (`SCNE`) from `.vscene`."""

    magic = SCNE_MAGIC
    version = 0
    export_flags = -1
    reserved = 0

    def read(self, reader: BinaryReader) -> None:

        self.magic = reader.read_uint32()
        self.version = reader.read_int32()

        if self.version >= 11:
            self.export_flags = reader.read_int32()
            self.reserved = reader.read_int32()
        else:
            self.export_flags = -1
            self.reserved = 0

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(self.magic)
        writer.write_int32(self.version)

        if self.version >= 11:
            writer.write_int32(self.export_flags)
            writer.write_int32(self.reserved)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "ScneChunk":

        value = ScneChunk()
        value.read(reader)

        return value
