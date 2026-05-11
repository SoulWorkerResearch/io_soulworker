
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class VisMaterialEffect(DataExchange_cl):

    version = 0
    library = ""
    name = ""
    param = ""
    template_name = ""

    def read(self, reader: BinaryReader) -> None:

        self.library = reader.read_utf8_uint32_string()
        self.name = reader.read_utf8_uint32_string()
        self.param = reader.read_utf8_uint32_string()

        if self.version >= 7:
            self.template_name = reader.read_utf8_uint32_string()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_utf8_uint32_string(self.library)
        writer.write_utf8_uint32_string(self.name)
        writer.write_utf8_uint32_string(self.param)

        if self.version >= 7:
            writer.write_utf8_uint32_string(self.template_name)

    @staticmethod
    def from_reader(reader: BinaryReader, version: int) -> 'VisMaterialEffect':

        value = VisMaterialEffect()
        value.version = version
        value.read(reader)

        return value
