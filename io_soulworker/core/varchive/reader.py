from __future__ import annotations

from collections.abc import Callable
from struct import unpack_from
from typing import Any

from mathutils import Matrix, Vector

from io_soulworker.core.varchive.objects import ArchiveObject


SerializeFn = Callable[["VArchiveReader", ArchiveObject], None]


class VArchiveError(ValueError):
    """Raised when SHPS / VArchive parsing fails."""


class _TypeSlot:
    """Placeholder for a VType* entry in the shared loadArray."""

    __slots__ = ("class_name", "schema")

    def __init__(self, class_name: str, schema: int) -> None:

        self.class_name = class_name
        self.schema = schema


class VArchiveReader:
    """Minimal Vision ``VArchive`` loader for SHPS object streams."""

    NEW_CLASS_TAG = 0xFFFFFFFF
    TYPE_INDEX_FLAG = 0x80000000

    def __init__(
        self,
        data: bytes | memoryview,
        *,
        loading_version: int,
        use_object_lengths: bool = True,
        has_per_object_range: bool = True,
        serializers: dict[str, SerializeFn] | None = None,
        aliases: dict[str, str] | None = None,
        leaf_skip_classes: set[str] | None = None,
        zone_file: bool = False,
        shallow_static_meshes: bool = False,
    ) -> None:

        self._data = memoryview(data)
        self._pos = 0
        self.loading_version = loading_version
        self.use_object_lengths = use_object_lengths
        self.has_per_object_range = has_per_object_range
        self.serializers = serializers if serializers is not None else {}
        self.aliases = aliases if aliases is not None else {}
        self.leaf_skip_classes = leaf_skip_classes if leaf_skip_classes is not None else set()
        # ``VZoneShapesArchive``: no per-object progress prefix; SMI local
        # version 0 is followed by 9 extra bytes before ``iVersion``.
        self.zone_file = zone_file
        # Read path/transform then skip the rest of the SMI payload (SGI).
        self.shallow_static_meshes = shallow_static_meshes
        self.current_payload_end: int | None = None
        # Vision::InitArchive seeds loadArray[0]=nullptr and m_nMapCount=1 so
        # object/type indices written to the stream are 1-based.
        self.load_array: list[Any] = [None]
        self.objects: list[ArchiveObject] = []
        self.skipped_classes: dict[str, int] = {}

    @property
    def position(self) -> int:

        return self._pos

    @property
    def remaining(self) -> int:

        return len(self._data) - self._pos

    def eof(self) -> bool:

        return self._pos >= len(self._data)

    def tell(self) -> int:

        return self._pos

    def seek(self, position: int) -> None:

        if position < 0 or position > len(self._data):
            raise VArchiveError(f"seek out of range: {position}")

        self._pos = position

    def read(self, size: int) -> bytes:

        if size < 0 or self._pos + size > len(self._data):
            raise VArchiveError(
                f"unexpected EOF at {
                    self._pos}: need {size}, have {
                    self.remaining}")

        start = self._pos
        self._pos += size

        return bytes(self._data[start:self._pos])

    def read_bool(self) -> bool:

        return self.read_uint8() != 0

    def read_uint8(self) -> int:

        return self.read(1)[0]

    def read_int8(self) -> int:

        value = self.read_uint8()

        return value - 256 if value >= 128 else value

    def read_uint16(self) -> int:

        value, = unpack_from("<H", self.read(2))

        return value

    def read_int16(self) -> int:

        value, = unpack_from("<h", self.read(2))

        return value

    def read_uint32(self) -> int:

        value, = unpack_from("<I", self.read(4))

        return value

    def read_int32(self) -> int:

        value, = unpack_from("<i", self.read(4))

        return value

    def read_int64(self) -> int:

        value, = unpack_from("<q", self.read(8))

        return value

    def read_uint64(self) -> int:

        value, = unpack_from("<Q", self.read(8))

        return value

    def read_float(self) -> float:

        value, = unpack_from("<f", self.read(4))

        return value

    def read_double(self) -> float:

        value, = unpack_from("<d", self.read(8))

        return value

    def read_string_binary(self) -> str:
        """``VArchive::ReadStringBinary`` — int32 length + bytes.

        Negative length means an empty string with no following bytes
        (Vision returns ``-1`` / ``0xFFFFFFFF`` for null/empty writes).
        """

        length = self.read_int32()

        if length <= 0:
            return ""

        raw = self.read(length)

        return raw.decode("cp949", errors="replace")

    def read_vstring(self) -> str:
        """``operator>>(VArchive, VString)`` — same as ReadStringBinary."""

        return self.read_string_binary()

    def read_compressed_int(self) -> int:
        """``VArchive::ReadCompressedInt`` — variable-length signed int."""

        lead = self.read_uint8()
        low = lead & 0x1F
        kind = lead & 0xE0

        if kind == 0:
            return low

        if kind == 0xA0:
            return -1 - low

        if kind == 0x20:
            return (low << 8) | self.read_uint8()

        if kind == 0x40:
            mid = self.read_uint8()
            return (low << 16) | (mid << 8) | self.read_uint8()

        if kind == 0x60:
            b1 = self.read_uint8()
            b2 = self.read_uint8()
            b3 = self.read_uint8()
            return (low << 24) | (b1 << 16) | (b2 << 8) | b3

        return self.read_uint32()

    def read_encrypted_string(self) -> str:
        """``VArchive::ReadEncryptedString`` — compressed length + XOR bytes.

        Each byte ``i`` is stored as ``plain ^ ((i + 17) * (i + 11))``.
        Negative length is an empty string.
        """

        length = self.read_compressed_int()

        if length < 0:
            return ""

        raw = self.read(length)
        plain = bytes(
            byte ^ (((index + 17) * (index + 11)) & 0xFF)
            for index, byte in enumerate(raw)
        )

        return plain.decode("cp949", errors="replace")

    def read_color_ref(self) -> int:
        """``VColorRef`` stored as little-endian RGBA uint32."""

        return self.read_uint32()

    def read_vis_vector(self) -> Vector:
        """``hkvVec3::SerializeAsVisVector`` — xyz + unused w."""

        x = self.read_float()
        y = self.read_float()
        z = self.read_float()
        self.read_float()

        return Vector((x, y, z))

    def read_vec2(self) -> Vector:

        return Vector((self.read_float(), self.read_float()))

    def read_vec3(self) -> Vector:
        """``SerializeX(hkvVec3)`` — three floats, no w."""

        return Vector(
            (self.read_float(),
             self.read_float(),
             self.read_float()))

    def read_vec4(self) -> Vector:

        return Vector((
            self.read_float(),
            self.read_float(),
            self.read_float(),
            self.read_float(),
        ))

    def read_mat3(self) -> Matrix:
        """``SerializeX(hkvMat3)`` — column-major 3×3 as 9 floats."""

        values = [self.read_float() for _ in range(9)]

        return Matrix((
            (values[0], values[3], values[6]),
            (values[1], values[4], values[7]),
            (values[2], values[5], values[8]),
        ))

    def read_mat4(self) -> Matrix:
        """``SerializeX(hkvMat4)`` — row groups of ElementsCM.

        Disk order is CM[0],CM[4],CM[8],CM[12], then CM[1],CM[5],… so each
        quartet is already one matrix row with translation in column 3.
        """

        floats = [self.read_float() for _ in range(16)]

        return Matrix((
            floats[0:4],
            floats[4:8],
            floats[8:12],
            floats[12:16],
        ))

    def read_bbox_vis(self) -> tuple[Vector, Vector]:
        """``SerializeAs_VisBoundingBox`` — two VisVectors."""

        return self.read_vis_vector(), self.read_vis_vector()

    def read_bbox_x(self) -> tuple[Vector, Vector]:
        """``SerializeX(hkvAlignedBBox)`` — two SerializeX vec3."""

        return self.read_vec3(), self.read_vec3()

    def read_class(self) -> tuple[str, int] | None:
        """``VArchive::ReadClass`` — class tag, may append a type slot."""

        tag = self.read_uint32()

        if tag == 0:
            return None

        if (tag & self.TYPE_INDEX_FLAG) == 0:
            raise VArchiveError(
                f"ReadClass got object tag #{tag} (expected a type index)"
            )

        return self._read_class(tag)

    def read_typed_object_reference(self) -> ArchiveObject | None:
        """``operator>>(VArchive, VTypedObjectReference)`` (loading)."""

        self.read_class()

        return self.read_object()

    def read_object(self, *, expected: str |
                    None = None) -> ArchiveObject | None:
        """``VShapesArchive::ReadObject`` + ``VArchive::ReadObject``."""

        if self.has_per_object_range:
            has_progress = self.read_bool()

            if has_progress:
                self.read_float()  # load-progress fraction (unused)

        return self._read_object_body(expected=expected)

    def read_proxy_object(self) -> ArchiveObject | None:
        """``VArchive::ReadProxyObject`` — nested ``ReadObject`` without type filter."""

        return self.read_object(expected=None)

    def _read_object_body(self, *, expected: str |
                          None) -> ArchiveObject | None:

        tag = self.read_uint32()

        if tag == 0:
            return None

        if (tag & self.TYPE_INDEX_FLAG) == 0:
            return self._object_reference(tag, expected=expected)

        class_name, schema = self._read_class(tag)
        payload_len: int | None = None
        payload_start = self._pos
        previous_payload_end = self.current_payload_end

        if self.use_object_lengths:
            payload_len = self.read_uint32()
            payload_start = self._pos
            self.current_payload_end = payload_start + payload_len
        else:
            self.current_payload_end = None

        obj = self._create_object(class_name)
        obj.archive_index = len(self.load_array)
        self.load_array.append(obj)
        self.objects.append(obj)

        handler_name = self.aliases.get(class_name, class_name)
        handler = self.serializers.get(handler_name)

        try:
            # Prefer an explicit serializer. Otherwise, with object lengths, skip
            # the opaque payload so large game scenes can still yield static
            # meshes. Classes that embed nested ReadObject MUST be registered
            # (see VModelSerializationProxy) — blind skips desync loadArray.
            if handler is None:
                if payload_len is None:
                    raise VArchiveError(
                        f"no serializer for class {class_name!r} "
                        f"(schema={schema}) at offset {payload_start}"
                    )

                self.skipped_classes[class_name] = (
                    self.skipped_classes.get(class_name, 0) + 1
                )
                self.seek(payload_start + payload_len)
                return obj

            if class_name in self.leaf_skip_classes and payload_len is not None:
                self.skipped_classes[class_name] = (
                    self.skipped_classes.get(class_name, 0) + 1
                )
                self.seek(payload_start + payload_len)
                return obj

            handler(self, obj)

            if payload_len is not None:
                consumed = self._pos - payload_start

                if consumed != payload_len:
                    raise VArchiveError(
                        f"{class_name}: object length mismatch "
                        f"(expected {payload_len}, consumed {consumed}) "
                        f"at payload start {payload_start}"
                    )

            if expected is not None and not self._is_compatible(
                    class_name, expected):
                raise VArchiveError(
                    f"type mismatch: got {class_name!r}, expected {expected!r}"
                )

            return obj
        finally:
            self.current_payload_end = previous_payload_end

    def _object_reference(
        self,
        index: int,
        *,
        expected: str | None,
    ) -> ArchiveObject:

        if index < 0 or index >= len(self.load_array):
            raise VArchiveError(f"object reference #{index} out of range")

        entry = self.load_array[index]

        if entry is None:
            raise VArchiveError(f"object reference #{index} is null sentinel")

        if isinstance(entry, _TypeSlot):
            raise VArchiveError(
                f"object reference #{index} points at a type slot")

        if not isinstance(entry, ArchiveObject):
            raise VArchiveError(
                f"object reference #{index} has unexpected type")

        if expected is not None and not self._is_compatible(
                entry.class_name, expected):
            raise VArchiveError(
                f"ref #{index} type mismatch: {
                    entry.class_name!r} vs {
                    expected!r}")

        return entry

    def _read_class(self, tag: int) -> tuple[str, int]:

        if tag == self.NEW_CLASS_TAG:
            schema = self.read_uint16()
            name_len = self.read_uint16()
            class_name = self.read(name_len).decode("ascii", errors="replace")
            self.load_array.append(_TypeSlot(class_name, schema))

            return class_name, schema

        type_index = tag & ~self.TYPE_INDEX_FLAG

        if type_index <= 0 or type_index >= len(self.load_array):
            raise VArchiveError(f"type index #{type_index} out of range")

        entry = self.load_array[type_index]

        if not isinstance(entry, _TypeSlot):
            raise VArchiveError(
                f"type index #{type_index} does not point at a class "
                f"(got {type(entry).__name__})"
            )

        return entry.class_name, entry.schema

    def _create_object(self, class_name: str) -> ArchiveObject:

        from io_soulworker.core.varchive import registry as reg

        return reg.create_object(class_name)

    @staticmethod
    def _is_compatible(actual: str, expected: str) -> bool:

        if actual == expected:
            return True

        # Soft check — Vision uses IsDerivedFrom; we only guard obvious cases.
        return True
