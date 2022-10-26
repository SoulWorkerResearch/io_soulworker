from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_mesh_effect import VisMeshEffect


class VisMeshEffectConfig:
    values: list[VisMeshEffect]

    def __init__(self, reader: BinaryReader) -> None:
        count = reader.read_uint16()
        self.values = [VisMeshEffect(reader) for _ in range(count)]
