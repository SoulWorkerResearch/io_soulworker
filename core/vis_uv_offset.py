from io import BufferedReader
from struct import unpack


class VisUVOffset:
    u: int
    v: int

    def __init__(self, model: BufferedReader) -> None:
        self.u, self.v = unpack("<BB", model.read(2))