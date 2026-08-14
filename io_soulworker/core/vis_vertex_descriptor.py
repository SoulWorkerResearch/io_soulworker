from logging import debug, warning

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class VisMBVertexDescriptor_cl(DataExchange_cl):

    MAGICK = 0x1020A0B
    MAX_TEXTURES = 16
    VERTEXDESC_OFFSET_MASK = 0x0FFF
    UNSET_OFFSET = 0xFFFF

    magick = 0
    header_size = 48
    stride = 32
    pos_offset = UNSET_OFFSET
    color_offset = UNSET_OFFSET
    normal_offset = UNSET_OFFSET
    tex_offset: list[int] = [UNSET_OFFSET] * MAX_TEXTURES
    secondary_color_offset = UNSET_OFFSET
    first_text_coord = 0
    last_text_coord = 0
    hash = 0

    def has_component(self, value: int) -> bool:

        return value != self.UNSET_OFFSET

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

            self.secondary_color_offset = self.UNSET_OFFSET

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(self.MAGICK)
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

        writer.write_uint32(self.MAGICK)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'VisMBVertexDescriptor_cl':

        value = VisMBVertexDescriptor_cl()
        value.read(reader)

        return value
