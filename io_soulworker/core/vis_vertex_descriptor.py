from __future__ import annotations

from dataclasses import dataclass
from logging import debug, warning

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


_KNOWN_SIZES = {
    "position": {0x3: 12},
    "normal": {0x3: 12, 0x0: 12},
    "color": {0x0: 4},
    "tex": {0x2: 8, 0x3: 12},
}
"""Bytes of a field per kind and format code. Position and normal are read
as three floats whatever their code says."""


def known_size(kind: str, code: int) -> int | None:
    """Bytes of a field the add-on decodes, ``None`` for any other format."""

    return _KNOWN_SIZES.get(kind, {}).get(code)


@dataclass(frozen=True)
class VertexComponent:
    """One field of a vertex, as the descriptor places it inside the stride.

    ``size`` comes from the format code for the formats the add-on decodes.
    A field with another format code has no known size or meaning: ``known``
    is ``False`` and ``size`` is the gap up to the next field (or the end of
    the stride), so the bytes can still be carried unchanged.
    """

    name: str
    kind: str
    slot: int
    code: int
    offset: int
    size: int
    known: bool


class VisMBVertexDescriptor_cl(DataExchange_cl):
    """Where each vertex field sits in the vertex buffer.

    Every 16-bit offset keeps the byte offset in the low 12 bits and a format
    code in the high nibble. Surveyed over all 26,541 shipped meshes, the
    fields tile the stride without gaps, and the codes seen are:

    * position: code 3, three floats (12 bytes), always at offset 0;
    * normal: code 3, three floats (12 bytes); two meshes carry code 0 on
      a field that is still twelve bytes of floats;
    * colour: code 0, four bytes;
    * texture coordinate slots 0, 1, 5 and 6: code 2, two floats (8 bytes);
    * texture coordinate slot 2: code 3, three floats (12 bytes).

    The secondary colour offset is never set.
    """

    MAGICK = 0x1020A0B
    MAX_TEXTURES = 16
    VERTEXDESC_OFFSET_MASK = 0x0FFF
    VERTEXDESC_FORMAT_SHIFT = 12
    UNSET_OFFSET = 0xFFFF

    FORMAT_BYTES4 = 0x0
    FORMAT_FLOAT2 = 0x2
    FORMAT_FLOAT3 = 0x3

    KIND_POSITION = "position"
    KIND_NORMAL = "normal"
    KIND_COLOR = "color"
    KIND_TEXTURE = "tex"
    KIND_SECONDARY_COLOR = "secondary_color"

    magick = 0
    header_size = 48
    stride = 32
    pos_offset = UNSET_OFFSET
    color_offset = UNSET_OFFSET
    normal_offset = UNSET_OFFSET
    tex_offset: list[int]
    secondary_color_offset = UNSET_OFFSET
    first_text_coord = 0
    last_text_coord = 0
    hash = 0

    def __init__(self) -> None:

        self.tex_offset = [self.UNSET_OFFSET] * self.MAX_TEXTURES

    def has_component(self, value: int) -> bool:

        return value != self.UNSET_OFFSET

    def offset_of(self, value: int) -> int:

        return value & self.VERTEXDESC_OFFSET_MASK

    def format_of(self, value: int) -> int:

        return value >> self.VERTEXDESC_FORMAT_SHIFT

    @classmethod
    def make_offset(cls, offset: int, code: int) -> int:

        return (code << cls.VERTEXDESC_FORMAT_SHIFT) | offset

    def components(self) -> list[VertexComponent]:
        """The fields the descriptor places, ordered by byte offset."""

        entries = [
            (self.KIND_POSITION, 0, self.pos_offset),
            (self.KIND_NORMAL, 0, self.normal_offset),
            (self.KIND_COLOR, 0, self.color_offset),
            (self.KIND_SECONDARY_COLOR, 0, self.secondary_color_offset),
        ] + [
            (self.KIND_TEXTURE, slot, value)
            for slot, value in enumerate(self.tex_offset)
        ]

        placed = sorted(
            (self.offset_of(value), kind, slot, self.format_of(value))
            for kind, slot, value in entries
            if self.has_component(value)
        )

        result: list[VertexComponent] = []

        for index, (offset, kind, slot, code) in enumerate(placed):

            size = known_size(kind, code)
            known = size is not None

            if size is None:

                following = (
                    placed[index + 1][0] if index + 1 < len(placed)
                    else self.stride
                )
                size = following - offset

            if size <= 0 or offset + size > self.stride:

                warning(
                    "Vertex field %s %d does not fit the %d byte stride",
                    kind, slot, self.stride)
                continue

            name = kind if kind != self.KIND_TEXTURE else "tex%d" % slot
            result.append(VertexComponent(
                name, kind, slot, code, offset, size, known))

        return result

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
