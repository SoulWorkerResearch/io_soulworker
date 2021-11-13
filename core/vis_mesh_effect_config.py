from io import BufferedReader
from struct import unpack

from io_soulworker.core.vis_mesh_effect import VisMeshEffect


class VisMeshEffectConfig:
    values: list[VisMeshEffect]

    def __init__(self, model: BufferedReader) -> None:
        count, = unpack("<H", model.read(2))
        self.values = [VisMeshEffect(model) for _ in range(count)]
