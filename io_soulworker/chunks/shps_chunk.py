from __future__ import annotations

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl
from io_soulworker.core.varchive.objects import (
    LightSource,
    Object3D,
    StaticMeshInstance,
)
from io_soulworker.core.varchive.shapes import read_shapes_payload

# FourCC keys used by VSceneLoader::ReadShapeChunk statistics
# (stored on disk as LE bytes of the big-endian `_XXX` codes).
SHPS_TYPE_ENT = int.from_bytes(b"_ENT", "big")
SHPS_TYPE_LGT = int.from_bytes(b"_LGT", "big")
SHPS_TYPE_PTG = int.from_bytes(b"_PTG", "big")
SHPS_TYPE_VOB = int.from_bytes(b"_VOB", "big")
SHPS_TYPE_SMI = int.from_bytes(b"_SMI", "big")
SHPS_TYPE_SGI = int.from_bytes(b"_SGI", "big")
SHPS_TYPE_MBO = int.from_bytes(b"_MBO", "big")
SHPS_TYPE_PTH = int.from_bytes(b"_PTH", "big")

SHPS_TYPE_NAMES = {
    SHPS_TYPE_ENT: "_ENT",
    SHPS_TYPE_LGT: "_LGT",
    SHPS_TYPE_PTG: "_PTG",
    SHPS_TYPE_VOB: "_VOB",
    SHPS_TYPE_SMI: "_SMI",
    SHPS_TYPE_SGI: "_SGI",
    SHPS_TYPE_MBO: "_MBO",
    SHPS_TYPE_PTH: "_PTH",
}


class ShpsTypeCount:

    key = 0
    count = 0

    def __init__(self, key: int = 0, count: int = 0) -> None:

        self.key = key
        self.count = count

    @property
    def name(self) -> str:

        return SHPS_TYPE_NAMES.get(self.key, f"0x{self.key:08x}")


# Back-compat alias used by tests / importers.
ShpsStaticMeshInstance = StaticMeshInstance


class ShpsChunk(DataExchange_cl):
    """Shapes archive (`SHPS`) — main object payload of a `.vscene`."""

    archive_version = 0
    object_count = 0
    non_null_count = 0
    root_object_count = 0
    reserved = 0
    type_counts: list[ShpsTypeCount]
    object_stream = b""
    static_meshes: list[StaticMeshInstance]
    entities: list[Object3D]
    lights: list[LightSource]
    scene_version = 14

    def __init__(self) -> None:

        self.type_counts = []
        self.static_meshes = []
        self.entities = []
        self.lights = []
        self.object_stream = b""
        self.scene_version = 14

    def read(
        self,
        reader: BinaryReader,
        length: int,
        *,
        scene_version: int = 14,
    ) -> None:

        start = reader.tell()
        self.scene_version = scene_version

        self.archive_version = reader.read_int32()
        self.object_count = reader.read_int32()
        self.non_null_count = reader.read_int32()
        self.root_object_count = reader.read_int32()
        self.reserved = reader.read_int32()

        stats_count = reader.read_int32()
        self.type_counts = []

        for _ in range(stats_count):
            key = reader.read_uint32()
            count = reader.read_int32()
            self.type_counts.append(ShpsTypeCount(key=key, count=count))

        consumed = reader.tell() - start
        remaining = length - consumed

        if remaining < 0:
            raise ValueError(
                f"SHPS header overran chunk length: header={consumed} length={length}"
            )

        self.object_stream = reader.read(remaining)

        if not self.object_stream:
            self.static_meshes = []
            self.entities = []
            self.lights = []
            return

        parsed = read_shapes_payload(
            self.object_stream,
            archive_version=self.archive_version,
            scene_version=scene_version,
        )
        self.static_meshes = parsed.static_meshes
        self.entities = parsed.entities
        self.lights = parsed.lights

    def write(self, writer: BinaryWriter) -> None:

        writer.write_int32(self.archive_version)
        writer.write_int32(self.object_count)
        writer.write_int32(self.non_null_count)
        writer.write_int32(self.root_object_count)
        writer.write_int32(self.reserved)

        writer.write_int32(len(self.type_counts))

        for entry in self.type_counts:
            writer.write_uint32(entry.key)
            writer.write_int32(entry.count)

        writer.write(self.object_stream)

    def type_count(self, key: int) -> int:

        for entry in self.type_counts:
            if entry.key == key:
                return entry.count

        return 0

    @staticmethod
    def from_reader(
        reader: BinaryReader,
        length: int,
        *,
        scene_version: int = 14,
    ) -> "ShpsChunk":

        value = ShpsChunk()
        value.read(reader, length, scene_version=scene_version)

        return value
