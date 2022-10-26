from logging import debug, warn
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_uv_offset import VisUVOffset


class VisVertexDescriptor(object):

    MAGICK = 0x1020A0B
    MAX_TEXTURES = 16

    stride: int
    """ Stride of the vertex structure; must be set to the size of the vertex structure. """

    pos_offset: int
    """ Offset of the position vector in the structure. Use bitwise OR with format bitflag constants of type VERTEXDESC_FORMAT_xyz to force a specific format. """

    color_offset: int
    """ Offset of the color vector in the structure. Use bitwise OR with format bitflag constants of type VERTEXDESC_FORMAT_xyz to force a specific format. """

    normal_offset: int
    """ Offset of the normal vector in the structure. Use bitwise OR with format bitflag constants of type VERTEXDESC_FORMAT_xyz to force a specific format. """

    tex_coord_offset: list[VisUVOffset]
    """ Offset of the sets of texture coordinates in the structure. Use bitwise OR with format bitflag constants of type VERTEXDESC_FORMAT_xyz to force a specific format. """

    secondary_color_offset: int
    """ Offset of the secondary color. Not supported on all platforms. """

    first_text_coord: int
    """ Index of the first used texture coordinate set. Set automatically by ComputeHash() or at serialization time. """

    last_text_coord: int
    """ Index of the last used texture coordinate set. Set automatically by ComputeHash() or at serialization time. """

    hash: int
    """ Hash value. Set automatically when computing the hash or at serialization time. """

    def __init__(self, reader: BinaryReader) -> None:

        magick = reader.read_uint32()
        assert self.MAGICK == magick

        self.version = reader.read_uint32()
        debug('version: %d', self.version)

        self.stride = reader.read_uint16()
        self.pos_offset = reader.read_uint16()
        self.color_offset = reader.read_uint16()
        self.normal_offset = reader.read_uint16()
        self.tex_coord_offset = list(self.__read_uv(reader))
        self.secondary_color_offset = reader.read_uint16()

        if self.version == 42:
            warn('Need recalc hash')

        if self.version == 48:
            self.first_text_coord = reader.read_uint8()
            self.last_text_coord = reader.read_uint8()
            self.hash = reader.read_uint32()

        if self.MAGICK == reader.read_uint32():
            self.secondary_color_offset = -1

    def __read_uv(self, reader: BinaryReader):
        for _ in range(self.MAX_TEXTURES):
            yield VisUVOffset(reader)

# https://youtu.be/UnIhRpIT7nc
