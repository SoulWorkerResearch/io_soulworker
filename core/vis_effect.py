from io import BufferedReader
from struct import unpack


class VisEffect:
    name: str
    flags: int

    def __init__(self, model: BufferedReader) -> None:
        length, = unpack("<I", model.read(4))
        self.name, = unpack("<%ss" % length, model.read(length))

        self.flags, = unpack("<I", model.read(4))
