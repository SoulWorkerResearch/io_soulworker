from io import SEEK_CUR, BufferedReader
from logging import debug
from os import fstat
from pathlib import Path
from struct import Struct, error as StructError, pack, unpack
from mathutils import Quaternion, Vector

from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_color import VisColor
from io_soulworker.core.vis_index_format import VisIndexFormat
from io_soulworker.core.vis_lighting_method import VisLightingMethod
from io_soulworker.core.vis_prim_type import VisPrimitiveType
from io_soulworker.core.vis_render_state_flags import VisRenderStateFlag
from io_soulworker.core.vis_surface_flags import VisSurfaceFlags
from io_soulworker.core.vis_transparency_type import VisTransparencyType


class TruncatedFileError(EOFError):
    """A read needed more bytes than the file has left.

    ``offset`` is where the read began, ``wanted`` the bytes it needed and
    ``available`` the bytes the file still had there. ``what`` names the part
    being read, when it is known.
    """

    def __init__(
            self,
            offset: int,
            wanted: int,
            available: int,
            what: str = "") -> None:

        self.offset = offset
        self.wanted = wanted
        self.available = available
        self.what = what

        detail = f" while reading {what}" if what else ""

        super().__init__(
            f"the file ends early: {wanted} byte(s) wanted at offset "
            f"{offset}, only {available} left{detail}"
        )


_INT8 = Struct("<b")
_UINT8 = Struct("<B")
_INT16 = Struct("<h")
_UINT16 = Struct("<H")
_INT32 = Struct("<i")
_UINT32 = Struct("<I")
_FLOAT = Struct("<f")


class BinaryReader(BufferedReader):

    FLOAT_MASK = 0x80000000

    def remaining(self) -> int:
        """Bytes between the read position and the end of the file."""

        return max(self._size - self.tell(), 0)

    def ensure_available(self, count: int, what: str = "") -> None:
        """Raise ``TruncatedFileError`` unless ``count`` bytes are left."""

        available = self.remaining()

        if count > available:

            raise TruncatedFileError(self.tell(), count, available, what)

    def _cut_short(self, wanted: int, data: bytes) -> TruncatedFileError:
        """The error for a read of ``wanted`` bytes that returned ``data``."""

        return TruncatedFileError(self.tell() - len(data), wanted, len(data))

    def read_vector2(self) -> Vector:
        return Vector([self.read_float() for _ in range(2)])

    def read_vector3(self) -> Vector:
        return Vector([self.read_float() for _ in range(3)])

    def read_vector4(self) -> Vector:
        return Vector([self.read_float() for _ in range(4)])

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
        self.ensure_available(length)
        self.seek(length, SEEK_CUR)

    @staticmethod
    def decode_game_string(value: bytes) -> str:
        """Length-prefixed strings are usually cp949; some later assets are UTF-8."""

        if not value:
            return ""

        for encoding in ("cp949", "utf-8"):
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                continue

        return value.decode("cp949", errors="replace")

    def read_utf8_uint32_string(self) -> str:
        length = self.read_uint32()

        # A damaged length must not ask for gigabytes.
        self.ensure_available(length)

        return BinaryReader.decode_game_string(self.read(length))

    def read_color(self) -> VisColor:
        return VisColor(*[self.read_uint8()
                        for _ in range(VisColor.COMPONENT_COUNT)])

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

    def read_render_state_flags(self) -> VisRenderStateFlag:
        return VisRenderStateFlag(self.read_uint16())

    def read_cid(self) -> VisChunkId:
        """ Chunk ID """
        value = self.read_int32()

        try:
            return VisChunkId(value)

        except Exception:

            debug(
                'Failed to parse chunk id from value: %s(%d)',
                VisChunkId.get_name(value),
                value
            )

            return VisChunkId.NONE

    def read_float(self) -> float:
        data = self.read(4)

        try:
            return _FLOAT.unpack(data)[0]
        except StructError:
            raise self._cut_short(4, data) from None

    def read_int8(self) -> int:
        data = self.read(1)

        try:
            return _INT8.unpack(data)[0]
        except StructError:
            raise self._cut_short(1, data) from None

    def read_uint8(self) -> int:
        data = self.read(1)

        try:
            return _UINT8.unpack(data)[0]
        except StructError:
            raise self._cut_short(1, data) from None

    def read_int16(self) -> int:
        data = self.read(2)

        try:
            return _INT16.unpack(data)[0]
        except StructError:
            raise self._cut_short(2, data) from None

    def read_uint16(self) -> int:
        data = self.read(2)

        try:
            return _UINT16.unpack(data)[0]
        except StructError:
            raise self._cut_short(2, data) from None

    def read_uint16_array(self, count: int):
        for _ in range(count):
            yield self.read_uint16()

    def read_uint32_array(self, count: int):
        for _ in range(count):
            yield self.read_uint32()

    def read_int32(self) -> int:
        data = self.read(4)

        try:
            return _INT32.unpack(data)[0]
        except StructError:
            raise self._cut_short(4, data) from None

    def read_uint32(self) -> int:
        data = self.read(4)

        try:
            return _UINT32.unpack(data)[0]
        except StructError:
            raise self._cut_short(4, data) from None

    def read_bool(self) -> bool:
        return bool(self.read_int8())

    def __init__(self, path: Path | str) -> None:
        super().__init__(open(path, "rb"))

        self._size = fstat(self.fileno()).st_size


#   https://youtu.be/K741PecDK3c
#
#   This video is no longer available because the YouTube account
#           associated with this video has been terminated.
