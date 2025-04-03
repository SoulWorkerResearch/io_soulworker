from io import SEEK_CUR, BufferedReader
from logging import debug
from pathlib import Path
from struct import pack, unpack

from mathutils import Quaternion, Vector

from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_color import VisColor
from io_soulworker.core.vis_index_format import VisIndexFormat
from io_soulworker.core.vis_lighting_method import VisLightingMethod
from io_soulworker.core.vis_prim_type import VisPrimitiveType
from io_soulworker.core.vis_render_state_flags import VisRenderStateFlag
from io_soulworker.core.vis_surface_flags import VisSurfaceFlags
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.file_import.animation.file_reader import VisBoundingBox


class BinaryReader(BufferedReader):

    FLOAT_MASK = 0x80000000

    def read_float_vector4(self) -> Vector:
        return Vector([self.read_float() for _ in range(4)])

    def read_float_vector3(self) -> Vector:
        return Vector([self.read_float() for _ in range(3)])

    def read_float_vector2(self) -> Vector:
        return Vector([self.read_float() for _ in range(2)])

    def read_quaternion(self) -> Quaternion:
        x = self.read_float()
        y = self.read_float()
        z = self.read_float()
        w = BinaryReader.__fxor__(self.read_float(), BinaryReader.FLOAT_MASK)

        return Quaternion((w, x, y, z))

    def read_quaternion3(self, default: float = 1.0) -> Quaternion:
        x = self.read_float()
        y = self.read_float()
        z = self.read_float()

        return Quaternion((default, x, y, z))

    @staticmethod
    def __fxor__(a: float, b: int) -> float:

        value = unpack('<I', pack('<f', a))[0]
        value ^= b
        value = unpack('<f', pack('<I', value))[0]

        return value

    def skip_utf8_uint32_string(self) -> None:
        length = self.read_uint32()
        self.seek(length, SEEK_CUR)

    def read_utf8_uint32_string(self) -> str:
        length = self.read_uint32()
        value, = unpack("<%ds" % length, self.read(length))

        # Korean encoding
        return value.decode('cp949')

    def read_color(self) -> VisColor:
        return VisColor(*[self.read_uint8() for _ in range(VisColor.COMPONENT_COUNT)])

    def read_primitive_type(self) -> VisPrimitiveType:
        return VisPrimitiveType(self.read_uint32())

    def read_surface_flags(self) -> VisSurfaceFlags:
        return VisSurfaceFlags(self.read_uint32())

    def read_lighting_method(self) -> VisLightingMethod:
        return VisLightingMethod(self.read_uint8())

    def read_index_format(self) -> VisIndexFormat:
        return VisIndexFormat(self.read_uint32())

    def read_transparency(self) -> VisTransparencyType:
        return VisTransparencyType(self.read_uint8())

    def read_bounding_box(self) -> VisBoundingBox:
        object = VisBoundingBox()

        object.min = self.read_float_vector3()
        object.max = self.read_float_vector3()

        return object

    def read_render_state_flags(self) -> VisRenderStateFlag:
        return VisRenderStateFlag(self.read_uint16())

    def read_cid(self) -> VisChunkId:
        """ Chunk ID """
        value = self.read_int32()

        try:
            return VisChunkId(value)

        except Exception:
            debug('Failed to parse chunk id from value: %d', value)
            return VisChunkId.NONE

    def read_float(self) -> float:
        return float(unpack("<f", self.read(4))[0])

    def read_int8(self) -> int:
        return int(unpack("<b", self.read(1))[0])

    def read_uint8(self) -> int:
        return int(unpack("<B", self.read(1))[0])

    def read_int16(self) -> int:
        return int(unpack("<h", self.read(2))[0])

    def read_uint16(self) -> int:
        return int(unpack("<H", self.read(2))[0])

    def read_uint16_array(self, count: int):
        for _ in range(count):
            yield self.read_uint16()

    def read_uint32_array(self, count: int):
        for _ in range(count):
            yield self.read_uint32()

    def read_int32(self) -> int:
        return int(unpack("<i", self.read(4))[0])

    def read_uint32(self) -> int:
        return int(unpack("<I", self.read(4))[0])

    def __init__(self, path: Path | str) -> None:
        super().__init__(open(path, "rb"))


#   https://youtu.be/K741PecDK3c
#
#   This video is no longer available because the YouTube account
#           associated with this video has been terminated.
