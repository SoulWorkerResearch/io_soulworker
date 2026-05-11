from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class CBPRChunk(DataExchange_cl):

    values: list[str]

    def __init__(self) -> None:

        self.values = []

    def read(self, reader: BinaryReader) -> None:

        count = reader.read_uint16()
        self.values = [reader.read_utf8_uint32_string() for _ in range(count)]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint16(len(self.values))

        for item in self.values:
            writer.write_utf8_uint32_string(item)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'CBPRChunk':

        value = CBPRChunk()
        value.read(reader)

        return value
