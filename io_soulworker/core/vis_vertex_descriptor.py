from logging import debug, warning

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class VisVertexDescriptor(DataExchange_cl):

    MAGICK = 0x1020A0B
    MAX_TEXTURES = 16
    VERTEXDESC_OFFSET_MASK = 0x0FFF

    magic = MAGICK
    header_size = 48
    stride = 0
    pos_offset = 0
    color_offset = 0
    normal_offset = 0
    tex_offset: list[int] = []
    secondary_color_offset = -1
    first_text_coord = 0
    last_text_coord = 0
    hash = 0

    def __init__(self) -> None:

        self.tex_offset = [0] * self.MAX_TEXTURES

    def has_component(self, value: int) -> bool:

        return value != -1

    def offset_of(self, value: int) -> int:

        return value & self.VERTEXDESC_OFFSET_MASK

    def read(self, reader: BinaryReader) -> None:

        self.magick = reader.read_uint32()
        assert self.MAGICK == self.magick

        self.header_size = reader.read_uint32()
        debug('version: %d', self.header_size)

        self.stride = reader.read_uint16()
        self.pos_offset = reader.read_uint16()
        self.color_offset = reader.read_uint16()
        self.normal_offset = reader.read_uint16()

        self.tex_offset = [
            reader.read_uint16()
            for _ in range(self.MAX_TEXTURES)
        ]

        self.secondary_color_offset = reader.read_uint16()

        if self.header_size == 42:

            warning('Need recalc hash')

        if self.header_size == 48:

            self.first_text_coord = reader.read_uint8()
            self.last_text_coord = reader.read_uint8()
            self.hash = reader.read_uint32()

        self.magick = reader.read_uint32()

        if self.magick == self.MAGICK:

            self.secondary_color_offset = -1

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(self.magic)
        writer.write_uint32(self.header_size)
        writer.write_uint16(self.stride)
        writer.write_uint16(self.pos_offset)
        writer.write_uint16(self.color_offset)
        writer.write_uint16(self.normal_offset)

        for i in range(self.MAX_TEXTURES):

            writer.write_uint16(self.tex_offset[i])

        writer.write_uint16(self.secondary_color_offset)

        if self.header_size == 48:

            writer.write_uint8(self.first_text_coord)
            writer.write_uint8(self.last_text_coord)
            writer.write_uint32(self.hash)

        writer.write_uint32(self.magick)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'VisVertexDescriptor':

        value = VisVertexDescriptor()
        value.read(reader)

        return value
