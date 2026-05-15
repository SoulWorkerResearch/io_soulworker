
from io import BufferedWriter
from struct import pack, unpack
from mathutils import Quaternion, Vector

from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_color import VisColor
from io_soulworker.core.vis_index_format import VisIndexFormat
from io_soulworker.core.vis_prim_type import VisPrimitiveType
from io_soulworker.core.vis_render_state_flags import VisRenderStateFlag
from io_soulworker.core.vis_transparency_type import VisTransparencyType


FLOAT_MASK = 0x80000000


def _fxor_float(a: float, b: int) -> float:

    value = unpack("<I", pack("<f", a))[0]
    value ^= b

    return unpack("<f", pack("<I", value))[0]


class BinaryWriter(BufferedWriter):

    def write_float(self, value: float) -> None:
        self.write(pack("<f", value))

    def write_int32(self, value: int) -> None:
        self.write(pack("<i", value))

    def write_uint32(self, value: int) -> None:
        self.write(pack("<I", value))

    def write_int16(self, value: int) -> None:
        self.write(pack("<h", value))

    def write_uint16(self, value: int) -> None:
        self.write(pack("<H", value))

    def write_uint8(self, value: int) -> None:
        self.write(pack("<B", value))

    def write_int8(self, value: int) -> None:
        self.write(pack("<b", value))

    def write_vector2(self, value: Vector) -> None:
        self.write(pack("<ff", value.x, value.y))

    def write_vector3(self, value: Vector) -> None:
        self.write(pack("<fff", value.x, value.y, value.z))

    def write_vector4(self, value: Vector) -> None:
        self.write(pack("<ffff", value.x, value.y, value.z, value.w))

    def write_quaternion(self, value: Quaternion) -> None:
        self.write_float(value.x)
        self.write_float(value.y)
        self.write_float(value.z)
        self.write_float(_fxor_float(value.w, FLOAT_MASK))

    def write_cid(self, value: VisChunkId) -> None:
        self.write_int32(int(value))

    def write_utf8_uint32_string(self, value: str) -> None:
        data = value.encode("cp949")
        self.write_uint32(len(data))
        self.write(data)

    def write_color(self, value: VisColor) -> None:
        self.write_uint8(value.r)
        self.write_uint8(value.g)
        self.write_uint8(value.b)
        self.write_uint8(value.a)

    def write_primitive_type(self, value: VisPrimitiveType) -> None:
        self.write_uint32(int(value))

    def write_index_format(self, value: VisIndexFormat) -> None:
        self.write_uint32(int(value))

    def write_transparency(self, value: VisTransparencyType) -> None:
        self.write_uint8(int(value))

    def write_render_state_flags(self, value: VisRenderStateFlag) -> None:
        self.write_uint16(int(value))
