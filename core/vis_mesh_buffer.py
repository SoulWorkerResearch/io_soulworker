
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.utility import indices_to_face
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_mesh_effect_config import VisMeshEffectConfig
from io_soulworker.core.vis_render_state import VisRenderState
from io_soulworker.core.vis_vertex_descriptor import VisVertexDescriptor


class VisMeshBuffer(object):

    MAGICK = 0x4455ABCD

    def __init__(self, chunk: VisChunkId, reader: BinaryReader) -> None:

        cid = reader.read_cid()
        assert cid == chunk

        self.loader_version = reader.read_uint32()
        assert self.loader_version == 1

        magick = reader.read_uint32()
        assert magick == self.MAGICK

        self.version = reader.read_uint32()

        self.descriptor = VisVertexDescriptor(reader)

        self.vertex_count = reader.read_uint32()
        iMemUsageFlagIndices = reader.read_uint8()

        if self.version >= 4:
            iBindFlagVertices = reader.read_uint8()

        if self.version >= 3:
            bMeshDataIsBigEndian = reader.read_uint8()

            _ = reader.read_uint16()
            """ Unused """

        prim_type = reader.read_uint32()
        index_count = reader.read_uint32()
        index_format = reader.read_uint32()
        current_prim_count = reader.read_uint32()
        mem_usage_flag_indices = reader.read_uint8()
        bind_flag_bertices = reader.read_uint8()
        vertices_double_buffered = reader.read_uint8()
        indices_double_buffered = reader.read_uint8()
        render_state = VisRenderState(reader)
        use_projection = reader.read_uint8()
        effect_config = VisMeshEffectConfig(reader)

        vertices = []
        uv_list = []
        for _ in range(self.vertex_count):
            t = reader.tell()

            pos = reader.read_vector()
            vertices.append([pos.x, pos.y, pos.z])

            tex_coord_offset = t + self.descriptor.tex_coord_offset[0].u
            reader.seek(tex_coord_offset)
            u = reader.read_float()

            tex_coord_offset = t + self.descriptor.tex_coord_offset[0].v
            reader.seek(tex_coord_offset)
            v = reader.read_float()

            uv_list.append([u, -v])

            reader.seek(t + self.descriptor.stride)

        count = current_prim_count * 3

        self.indices = reader.read_uint16_array(count)
        self.faces = list(indices_to_face(self.indices))
