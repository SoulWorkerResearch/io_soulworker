from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class VisEffectConfig_cl(DataExchange_cl):

    shader_library_name = ""
    effect_name = ""
    effect_params = ""

    creation_flags = 0

    def read(self, reader: BinaryReader) -> None:

        self.shader_library_name = reader.read_utf8_uint32_string()
        self.effect_name = reader.read_utf8_uint32_string()
        self.effect_params = reader.read_utf8_uint32_string()

        self.creation_flags = reader.read_uint32()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_utf8_uint32_string(self.shader_library_name)
        writer.write_utf8_uint32_string(self.effect_name)
        writer.write_utf8_uint32_string(self.effect_params)

        writer.write_uint32(self.creation_flags)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'VisEffectConfig_cl':

        value = VisEffectConfig_cl()
        value.read(reader)

        return value
