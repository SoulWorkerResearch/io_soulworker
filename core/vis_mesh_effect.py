from io import BufferedReader
from struct import unpack

from io_soulworker.core.utility import read_string


class VisMeshEffect:
    name: str
    flags: int

    def __init__(self, model: BufferedReader) -> None:
        self.name = read_string(model)

        self.flags, = unpack("<I", model.read(4))
