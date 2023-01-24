from logging import debug

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.utility import indices_to_face
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_index_format import VisIndexFormat
from io_soulworker.core.vis_vertex_descriptor import VisVertexDescriptor
from io_soulworker.core.vis_render_state import VisRenderState
from io_soulworker.core.vis_mesh_effect_config import VisMeshEffectConfig


class VMshChunk(object):

    MAGICK = 0x4455ABCD

    VERTEXT_USAGE_FLAGS = -1
    INDEX_USAGE_FLAGS = -1
    VERTEX_BIND_FLAGS = -1
    INDEX_BIND_FLAGS = -1

    def __init__(self, id: VisChunkId, reader: BinaryReader) -> None:

        cid = reader.read_cid()
        assert cid == id

        self.loader_version = reader.read_uint32()
        assert self.loader_version == 1

        magick = reader.read_uint32()
        assert magick == self.MAGICK

        self.version = reader.read_uint32()

        self.descriptor = VisVertexDescriptor(reader)

        self.vertex_count = reader.read_uint32()

        vertex_usage_flags = reader.read_uint8()
        self.m_iMemUsageFlagVertices = vertex_usage_flags if self.VERTEXT_USAGE_FLAGS == \
            -1 else self.VERTEXT_USAGE_FLAGS

        if self.version >= 4:
            iBindFlagVertices = reader.read_uint8()

        if self.version >= 3:
            self.bMeshDataIsBigEndian = reader.read_uint8()

            _ = reader.read_uint16()
            """ Unused """

        self.prim_type = reader.read_primitive_type()
        self.index_count = reader.read_uint32()
        self.index_format = reader.read_index_format()
        self.current_prim_count = reader.read_uint32()
        self.mem_usage_flag_indices = reader.read_uint8()

        if (self.version >= 4):
            iBindFlagIndices = reader.read_uint8()

        self.vertices_double_buffered = reader.read_uint8()
        self.indices_double_buffered = reader.read_uint8()

        self.render_state = VisRenderState(reader)

        self.use_projection = reader.read_uint8()
        self.texture_channels_count = reader.read_uint8()

        self.effect_config = VisMeshEffectConfig(reader)

        if (self.version == 5):
            _ = reader.read_uint8()

        indices_offset = reader.tell() + self.descriptor.stride * self.vertex_count

        self.vertices = []
        self.normals = []
        self.uvs = []

        for _ in range(self.vertex_count):
            t = reader.tell()

            if (self.descriptor.hasComponent(self.descriptor.pos_offset)):
                offset = self.descriptor.offsetOf(self.descriptor.pos_offset)
                reader.seek(t + offset)

                pos = reader.read_float_vector3()
                self.vertices.append([pos.x, pos.y, pos.z])

            if (self.descriptor.hasComponent(self.descriptor.normal_offset)):
                offset = self.descriptor.offsetOf(
                    self.descriptor.normal_offset)
                reader.seek(t + offset)

                normal = reader.read_float_vector3()
                self.normals.append([normal.x, normal.y, normal.z])

            if (self.descriptor.hasComponent(self.descriptor.tex_offset[0])):
                offset = self.descriptor.offsetOf(
                    self.descriptor.tex_offset[0])
                reader.seek(t + offset)

                texture = reader.read_float_vector3()
                self.uvs.append([texture.x, -texture.y])

            reader.seek(t + self.descriptor.stride)

        reader.seek(indices_offset)

        self.indices = list(self.__indices(reader))

        vertices_per_face = self.index_count // self.current_prim_count
        self.faces = list(indices_to_face(self.indices, vertices_per_face))
        _ = 1

    def __indices(self, reader: BinaryReader):
        match self.index_format:
            case VisIndexFormat._16:
                return reader.read_uint16_array(self.index_count)
            case VisIndexFormat._32:
                return reader.read_uint32_array(self.index_count)
