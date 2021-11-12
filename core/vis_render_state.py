from io import BufferedReader
from struct import unpack


class VisRenderState:
    transp_mode: int
    unused: int
    render_flags: int

    def __init__(self, model: BufferedReader) -> None:
        self.transp_mode, = unpack("<B", model.read(1))
        self.unused, = unpack("<B", model.read(1))
        self.render_flags, = unpack("<H", model.read(2))
