from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class HeadChunk(DataExchange_cl):

    sequence_count = 0

    def read(self, reader: BinaryReader) -> None:

        self.sequence_count = reader.read_uint32()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(self.sequence_count)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'HeadChunk':

        value = HeadChunk()
        value.read(reader)

        return value
