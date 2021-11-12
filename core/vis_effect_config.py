from io import BufferedReader
from struct import unpack

from io_soulworker.core.vis_effect import VisEffect


class VisEffectConfig:
    values: list[VisEffect]

    def __init__(self, model: BufferedReader) -> None:
        count, = unpack("<H", model.read(2))
        self.values = [VisEffect(model) for _ in range(count)]
