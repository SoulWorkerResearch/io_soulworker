from struct import pack_into

from mathutils import Vector

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl
from io_soulworker.core.utility import indices_to_face
from io_soulworker.core.vis_bounding_box import HavokBoundingBox
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_index_format import VisIndexFormat
from io_soulworker.core.vis_mesh_effect_config import VisEffectConfig_cl
from io_soulworker.core.vis_render_state import VisRenderState
from io_soulworker.core.vis_vertex_descriptor import VisMBVertexDescriptor_cl


class VMshChunk(DataExchange_cl):

    MAGICK = 0x4455ABCD
    LOADER_VERSION = 1
    LOCAL_VERSION = 5

    VERTEXT_USAGE_FLAGS = -1
    INDEX_USAGE_FLAGS = -1
    VERTEX_BIND_FLAGS = -1
    INDEX_BIND_FLAGS = -1

    chunk_id = VisChunkId.NONE

    loader_version = LOADER_VERSION
    version = LOCAL_VERSION
    vertex_count = 0
    usage_flag_vertices = 0
    bind_flag_vertices = 0
    mesh_data_is_big_endian = False
    unused_1 = 0
    prim_type = 0
    index_count = 0
    index_format = VisIndexFormat._16
    current_prim_count = 0
    mem_usage_flag_indices = 0
    bind_flag_indices = 0
    vertices_double_buffered = 0
    indices_double_buffered = 0
    double_buffering_from_file = 0
    use_projection = 0
    texture_channels_count = 0
    texture_channel_paths: list[str] = []
    descriptor = VisMBVertexDescriptor_cl()
    render_state = VisRenderState()
    effect_config = VisEffectConfig_cl()
    bounding_box = HavokBoundingBox()
    unused = 0
    vertices: list[Vector] = []
    normals: list[Vector] = []
    uvs: list[Vector] = []
    indices: list[int] = []
    faces: list[list[int]] = []

    DEFAULT_TEXTURE_CHANNEL_COUNT = 16

    def read(self, reader: BinaryReader) -> None:

        cid = reader.read_cid()
        assert cid == self.chunk_id

        self.loader_version = reader.read_uint32()
        assert self.loader_version == self.LOADER_VERSION

        magick = reader.read_uint32()
        assert magick == self.MAGICK

        self.version = reader.read_uint32()
        assert self.version < self.LOCAL_VERSION

        self.descriptor.read(reader)
        self.vertex_count = reader.read_uint32()
        self.usage_flag_vertices = reader.read_uint8()

        if self.version >= 4:

            self.bind_flag_vertices = reader.read_uint8()

        if self.version >= 3:

            self.mesh_data_is_big_endian = reader.read_bool()

            self.unused_1 = reader.read_uint16()

        self.prim_type = reader.read_primitive_type()
        self.index_count = reader.read_uint32()
        self.index_format = reader.read_index_format()
        self.current_prim_count = reader.read_uint32()
        self.mem_usage_flag_indices = reader.read_uint8()

        if self.version >= 4:

            self.bind_flag_indices = reader.read_uint8()

        self.vertices_double_buffered = reader.read_uint8()
        self.indices_double_buffered = reader.read_uint8()

        if self.version >= 5:

            self.double_buffering_from_file = reader.read_uint8()

        self.render_state.read(reader)

        self.use_projection = reader.read_uint8()
        self.texture_channels_count = reader.read_uint8()
        self.texture_channel_paths = [
            reader.read_utf8_uint32_string()
            for _ in range(self.texture_channels_count)
        ]

        self.effect_config.read(reader)

        indices_offset = reader.tell() + self.descriptor.stride * self.vertex_count

        self.vertices = []
        self.normals = []
        self.uvs = []

        for _ in range(self.vertex_count):

            t = reader.tell()

            if self.descriptor.has_component(self.descriptor.pos_offset):

                off = self.descriptor.offset_of(self.descriptor.pos_offset)
                reader.seek(t + off)

                pos = reader.read_vector3()
                self.vertices.append(pos)

            # TODO: normals are not used in the current implementation
            # if self.descriptor.has_component(self.descriptor.normal_offset):

            #     off = self.descriptor.offset_of(self.descriptor.normal_offset)
            #     reader.seek(t + off)

            #     normal = reader.read_vector3()
            #     self.normals.append(normal)

            if self.descriptor.has_component(self.descriptor.tex_offset[0]):

                off = self.descriptor.offset_of(self.descriptor.tex_offset[0])
                reader.seek(t + off)

                texture = reader.read_vector2()
                texture.y *= -1

                self.uvs.append(texture)

            reader.seek(t + self.descriptor.stride)

        reader.seek(indices_offset)

        self.indices = list(self.__indices(reader))

        vertices_per_face = self.index_count // self.current_prim_count
        self.faces = list(indices_to_face(self.indices, vertices_per_face))

        self.bounding_box = HavokBoundingBox.from_reader(reader)
        self.unused = reader.read_int32()

    def write(self, writer: BinaryWriter) -> None:
        writer.write_cid(self.chunk_id)
        writer.write_uint32(self.loader_version)
        writer.write_uint32(self.MAGICK)
        writer.write_uint32(self.version)

        self.descriptor.write(writer)

        vertex_count = self.__vertex_count_for_write()
        writer.write_uint32(vertex_count)
        writer.write_uint8(self.usage_flag_vertices)

        if self.version >= 4:

            writer.write_uint8(self.bind_flag_vertices)

        if self.version >= 3:

            writer.write_uint8(1 if self.mesh_data_is_big_endian else 0)
            writer.write_uint16(self.unused_1)

        writer.write_primitive_type(self.prim_type)

        indices = self.__indices_for_write()
        index_count = len(indices)
        current_prim_count = self.__prim_count_for_write(index_count)

        writer.write_uint32(index_count)
        writer.write_index_format(self.index_format)
        writer.write_uint32(current_prim_count)
        writer.write_uint8(self.mem_usage_flag_indices)

        if self.version >= 4:

            writer.write_uint8(self.bind_flag_indices)

        writer.write_uint8(self.vertices_double_buffered)
        writer.write_uint8(self.indices_double_buffered)

        if self.version >= 5:

            writer.write_uint8(self.double_buffering_from_file)

        self.render_state.write(writer)
        writer.write_uint8(self.use_projection)

        texture_channel_paths = self.__texture_channel_paths_for_write()
        writer.write_uint8(len(texture_channel_paths))

        for channel_path in texture_channel_paths:
            writer.write_utf8_uint32_string(channel_path)

        self.effect_config.write(writer)

        self.__write_vertices(writer, vertex_count)
        self.__write_indices(writer, indices)

        self.bounding_box.write(writer)
        writer.write_int32(self.unused)

        # Keep in-memory metadata consistent after save.
        self.vertex_count = vertex_count
        self.index_count = index_count
        self.current_prim_count = current_prim_count
        self.indices = indices
        self.faces = list(indices_to_face(indices, 3))
        self.texture_channels_count = len(texture_channel_paths)
        self.texture_channel_paths = texture_channel_paths

    def __indices(self, reader: BinaryReader):

        match self.index_format:

            case VisIndexFormat._16:
                return reader.read_uint16_array(self.index_count)

            case VisIndexFormat._32:
                return reader.read_uint32_array(self.index_count)

        raise ValueError("Unknown indices type")

    def __vertex_count_for_write(self) -> int:

        return len(self.vertices)

    def __indices_for_write(self) -> list[int]:

        if self.indices:

            return [int(i) for i in self.indices]

        if not self.faces:

            return []

        return [int(index) for face in self.faces for index in face]

    def __prim_count_for_write(self, index_count: int) -> int:

        if self.current_prim_count:

            return self.current_prim_count

        if self.faces:

            return len(self.faces)

        if index_count and index_count % 3 == 0:

            return index_count // 3

        return 0

    def __write_vertices(self, writer: BinaryWriter, vertex_count: int) -> None:

        stride = self.descriptor.stride

        if stride <= 0:

            return

        for index in range(vertex_count):

            raw = bytearray(stride)

            if self.descriptor.has_component(self.descriptor.pos_offset):

                off = self.descriptor.offset_of(self.descriptor.pos_offset)
                x, y, z = self.__vector3_at(self.vertices, index)
                pack_into("<fff", raw, off, x, y, z)

            if self.descriptor.has_component(self.descriptor.normal_offset):

                off = self.descriptor.offset_of(self.descriptor.normal_offset)
                x, y, z = self.__vector3_at(self.normals, index)
                pack_into("<fff", raw, off, x, y, z)

            if self.descriptor.has_component(self.descriptor.tex_offset[0]):

                off = self.descriptor.offset_of(self.descriptor.tex_offset[0])
                u, v = self.__vector2_at(self.uvs, index)
                pack_into("<ff", raw, off, u, -v)

            writer.write(raw)

    def __write_indices(self, writer: BinaryWriter, indices: list[int]) -> None:

        match self.index_format:

            case VisIndexFormat._16:
                for index in indices:
                    writer.write_uint16(index)

            case VisIndexFormat._32:
                for index in indices:
                    writer.write_uint32(index)

            case _:
                raise ValueError("Unknown indices type")

    def __texture_channel_paths_for_write(self) -> list[str]:

        if self.texture_channel_paths:
            return [str(path) for path in self.texture_channel_paths]

        if self.texture_channels_count > 0:
            return [""] * self.texture_channels_count

        return [""] * self.DEFAULT_TEXTURE_CHANNEL_COUNT

    def __vector3_at(self, data: list, index: int) -> tuple[float, float, float]:

        if index >= len(data):
            return (0.0, 0.0, 0.0)

        value = data[index]
        return (float(value[0]), float(value[1]), float(value[2]))

    def __vector2_at(self, data: list, index: int) -> tuple[float, float]:

        if index >= len(data):
            return (0.0, 0.0)

        value = data[index]

        return (float(value[0]), float(value[1]))

    @staticmethod
    def from_reader(chunk_id: VisChunkId, reader: BinaryReader) -> 'VMshChunk':

        value = VMshChunk()

        value.chunk_id = chunk_id
        value.read(reader)

        return value
