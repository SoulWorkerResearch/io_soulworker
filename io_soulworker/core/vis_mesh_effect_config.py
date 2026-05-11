from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl
from io_soulworker.core.vis_mesh_effect import VisEffectConfig_cl


class VisEffectConfig_cl(DataExchange_cl):

    values: list[VisEffectConfig_cl] = []

    def read(self, reader: BinaryReader) -> None:

        count = reader.read_uint16()

        self.values = [
            VisEffectConfig_cl.from_reader(reader)
            for _ in range(count)
        ]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint16(len(self.values))

        for effect in self.values:
            effect.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'VisEffectConfig_cl':

        value = VisEffectConfig_cl()
        value.read(reader)

        return value
