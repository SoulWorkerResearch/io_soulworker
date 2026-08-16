from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class EplgChunk(DataExchange_cl):
    """Referenced engine plugins (`EPLG`) from `.vscene`."""

    plugins: list[str]

    def __init__(self) -> None:

        self.plugins = []

    def read(self, reader: BinaryReader) -> None:

        count = reader.read_uint32()
        self.plugins = [
            reader.read_utf8_uint32_string()
            for _ in range(count)
        ]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(len(self.plugins))

        for name in self.plugins:
            writer.write_utf8_uint32_string(name)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "EplgChunk":

        value = EplgChunk()
        value.read(reader)

        return value
