from logging import debug

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.utility import indices_to_face
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_vertex_descriptor import VisVertexDescriptor
from io_soulworker.core.vis_render_state import VisRenderState
from io_soulworker.core.vis_mesh_effect_config import VisMeshEffectConfig


class VisMeshChunk(object):

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
            debug('unsupported version')
            raise

        if self.version >= 3:
            self.bMeshDataIsBigEndian = reader.read_uint8()

            _ = reader.read_uint16()
            """ Unused """

        self.prim_type = reader.read_uint32()
        self.index_count = reader.read_uint32()
        self.index_format = reader.read_uint32()
        self.current_prim_count = reader.read_uint32()
        self.mem_usage_flag_indices = reader.read_uint8()

        if (self.version < 4):
            pass
        else:
            debug('unsupported version')
            raise

        self.vertices_double_buffered = reader.read_uint8()
        self.indices_double_buffered = reader.read_uint8()

        self.render_state = VisRenderState(reader)

        self.use_projection = reader.read_uint8()
        self.texture_channels_count = reader.read_uint8()

        self.effect_config = VisMeshEffectConfig(reader)

        self.vertices = []
        self.uv_list = []
        for _ in range(self.vertex_count):
            t = reader.tell()

            reader.seek(t + self.descriptor.pos_offset.x)
            pos = reader.read_vector()

            self.vertices.append([pos.x, pos.y, pos.z])

            reader.seek(t + self.descriptor.tex_coord_offset[0].x)
            u = reader.read_float()
            v = reader.read_float()

            self.uv_list.append([u, -v])

            reader.seek(t + self.descriptor.stride)

        self.indices = list(reader.read_uint16_array(self.vertex_count))
        self.faces = list(indices_to_face(self.indices))
