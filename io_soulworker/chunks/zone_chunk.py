from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class ZoneChunk(DataExchange_cl):
    """Zone summary (`ZONE`) from `.vscene`."""

    zone_count = 0
    reserved = 0

    def read(self, reader: BinaryReader) -> None:

        self.zone_count = reader.read_int32()
        self.reserved = reader.read_int32()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_int32(self.zone_count)
        writer.write_int32(self.reserved)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "ZoneChunk":

        value = ZoneChunk()
        value.read(reader)

        return value
