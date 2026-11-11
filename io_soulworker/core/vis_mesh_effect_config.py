from ..core.binary_reader import BinaryReader
from ..core.binary_writer import BinaryWriter
from ..core.data_exchange import DataExchange_cl
from ..core.vis_mesh_effect import (
    VisEffectConfig_cl as VisEffectConfigItem_cl,
)


class VisEffectConfig_cl(DataExchange_cl):
    """List of effect configurations of a mesh; every entry is a
    ``VisEffectConfigItem_cl`` (``VisEffectConfig_cl`` in ``vis_mesh_effect``)."""

    values: list[VisEffectConfigItem_cl]

    def __init__(self) -> None:

        self.values = []

    def read(self, reader: BinaryReader) -> None:

        count = reader.read_uint16()

        self.values = [
            VisEffectConfigItem_cl.from_reader(reader)
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
