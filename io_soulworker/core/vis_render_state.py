from io_soulworker.core.binary_reader import BinaryReader


class VisRenderState:
    def __init__(self, reader: BinaryReader) -> None:
        self.transp_mode = reader.read_uint8()
        self.unused = reader.read_uint8()
        self.render_flags = reader.read_uint16()
