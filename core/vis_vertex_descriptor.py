from io import BufferedReader
from struct import unpack
from io_soulworker.core.vis_uv_offset import VisUVOffset


class VisVertexDescriptor:
    MAGICK = 0x1020A0B

    stride: int
    pos_offset: int
    color_offset: int
    normal_offset: int
    tex_coord_offset: list[VisUVOffset]
    secondary_color_offset: int
    first_text_coord: int
    last_text_coord: int
    hash: int

    def __init__(self, model: BufferedReader) -> None:
        magick, = unpack("<I", model.read(4))
        assert self.MAGICK == magick

        v6, = unpack("<i", model.read(4))
        # assert v6 <= 48

        self.stride, = unpack("<H", model.read(2))
        self.pos_offset, = unpack("<H", model.read(2))
        self.color_offset, = unpack("<H", model.read(2))
        self.normal_offset, = unpack("<H", model.read(2))
        self.tex_coord_offset = [VisUVOffset(model) for _ in range(16)]
        self.secondary_color_offset, = unpack(
            "<H", model.read(2))

        # assert 42 != v6

        if 48 == v6:
            self.first_text_coord, = unpack("<B", model.read(1))
            self.last_text_coord, = unpack("<B", model.read(1))
            self.hash, = unpack("<I", model.read(4))

        magick, = unpack("<I", model.read(4))
        assert self.MAGICK == magick
