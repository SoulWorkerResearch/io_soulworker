from mathutils import Vector

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl
from io_soulworker.core.vis_bounding_box import HavokBoundingBox


class VisMeshBuffer_cl(DataExchange_cl):

    geometry_info_count: int = 0
    format_version: int = 0

    indices_start = 0
    indices_count = 0
    unused_1_1 = 0
    unused_1_2 = 0
    first_vertex = 0
    num_vertices = 0
    unused_1_3 = 0
    unused_1_4 = 0

    local_bounds = HavokBoundingBox()

    surface_index = 0

    geometry_index = 0

    unused_2_1 = 0
    unused_2_2 = 0
    unused_2_3 = 0
    unused_2_4 = 0
    unused_2_5 = 0
    unused_2_6 = 0.0
    unused_2_7 = 0.0

    def read(self, reader: BinaryReader) -> None:

        self.indices_start = reader.read_uint32()
        self.indices_count = reader.read_uint32()
        self.unused_1_1 = reader.read_uint32()
        self.unused_1_2 = reader.read_uint32()
        self.first_vertex = reader.read_uint32()
        self.num_vertices = reader.read_uint32()
        self.unused_1_3 = reader.read_uint32()
        self.unused_1_4 = reader.read_uint32()

        self.local_bounds.read(reader)

        self.surface_index = reader.read_int32()

        if self.format_version < 2:

            if self.format_version == 1:

                self.unused_2_1 = reader.read_int32()
                self.unused_2_2 = reader.read_int16()
                self.unused_2_3 = reader.read_int16()
                self.unused_2_4 = reader.read_int8()
                self.unused_2_5 = reader.read_int8()
                self.unused_2_6 = reader.read_float()
                self.unused_2_7 = reader.read_float()

        else:

            self.geometry_index = reader.read_int32()
            if self.geometry_info_count > 0:
                assert 0 <= self.geometry_index < self.geometry_info_count

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(self.indices_start)
        writer.write_uint32(self.indices_count)
        writer.write_uint32(self.unused_1_1)
        writer.write_uint32(self.unused_1_2)
        writer.write_uint32(self.first_vertex)
        writer.write_uint32(self.num_vertices)
        writer.write_uint32(self.unused_1_3)
        writer.write_uint32(self.unused_1_4)

        self.local_bounds.write(writer)

        writer.write_int32(self.surface_index)

        if self.format_version < 2:

            if self.format_version == 1:

                writer.write_uint32(self.unused_2_1)
                writer.write_uint16(self.unused_2_2)
                writer.write_uint16(self.unused_2_3)
                writer.write_uint8(self.unused_2_4)
                writer.write_uint8(self.unused_2_5)
                writer.write_float(self.unused_2_6)
                writer.write_float(self.unused_2_7)

        else:

            writer.write_int32(self.geometry_index)

    @staticmethod
    def from_reader(
        reader: BinaryReader,
        *,
        format_version: int,
        geometry_info_count: int = 0,
    ) -> 'VisMeshBuffer_cl':

        value = VisMeshBuffer_cl()

        value.format_version = format_version
        value.geometry_info_count = geometry_info_count
        value.read(reader)

        return value


class VisBaseGeometryInfo(DataExchange_cl):

    LOCAL_VERSION = 8

    version = LOCAL_VERSION

    tag = 0
    visible_mask = 0
    light_mask = 0
    trace_mask = 0
    flags = 0
    user_flags = 0
    near_clip_distance = 0.0
    far_clip_distance = 0.0
    clip_reference = Vector()
    name = ""
    lod_index = 0

    def read(self, reader: BinaryReader) -> None:

        self.tag = reader.read_uint32()
        self.visible_mask = reader.read_uint32()
        self.light_mask = reader.read_uint16()
        self.trace_mask = reader.read_uint16()
        self.flags = reader.read_uint16()
        self.user_flags = reader.read_uint16()
        self.near_clip_distance = reader.read_float()
        self.far_clip_distance = reader.read_float()
        self.clip_reference = reader.read_vector3()

        if self.version >= 3:

            self.name = reader.read_utf8_uint32_string()

        if self.version >= 4:

            self.lod_index = reader.read_int16()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(self.tag)
        writer.write_uint32(self.visible_mask)
        writer.write_uint16(self.light_mask)
        writer.write_uint16(self.trace_mask)
        writer.write_uint16(self.flags)
        writer.write_uint16(self.user_flags)
        writer.write_float(self.near_clip_distance)
        writer.write_float(self.far_clip_distance)
        writer.write_vector3(self.clip_reference)

        if self.version >= 3:
            writer.write_utf8_uint32_string(self.name)

        if self.version >= 4:
            writer.write_int16(self.lod_index)

    @staticmethod
    def from_reader(reader: BinaryReader, version: int) -> 'VisBaseGeometryInfo':

        value = VisBaseGeometryInfo()

        value.version = version
        value.read(reader)

        return value


class VisSubMeshChunk(DataExchange_cl):

    unknown = 0
    version = 0
    meshes: list[VisMeshBuffer_cl] = []
    geometry_info: list[VisBaseGeometryInfo] = []

    def read(self, reader: BinaryReader) -> None:

        self.unknown = reader.read_int32()

        if self.unknown >= 0:

            return

        self.version = reader.read_int32()

        mesh_count = 0

        if self.version >= 2:

            geometry_count = reader.read_int32()

            self.geometry_info = [
                VisBaseGeometryInfo.from_reader(reader, version=self.version)
                for _ in range(geometry_count)
            ]

            mesh_count = reader.read_int32()

            if mesh_count < 0:
                raise ValueError(f"Invalid sub mesh count: {mesh_count}")

        self.meshes = [
            VisMeshBuffer_cl.from_reader(
                reader,
                format_version=self.version,
                geometry_info_count=len(self.geometry_info),
            )
            for _ in range(mesh_count)
        ]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_int32(self.unknown)

        if self.unknown >= 0:
            return

        writer.write_int32(self.version)

        if self.version >= 2:

            writer.write_int32(len(self.geometry_info))

            for geometry_info in self.geometry_info:

                geometry_info.version = self.version
                geometry_info.write(writer)

        mesh_count = len(self.meshes)

        writer.write_int32(mesh_count)

        for mesh in self.meshes:

            mesh.format_version = self.version
            mesh.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'VisSubMeshChunk':

        value = VisSubMeshChunk()
        value.read(reader)

        return value
