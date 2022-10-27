from pathlib import Path
from logging import debug

from io_soulworker.chunks.vis_mesh_chunk import VisMeshChunk
from io_soulworker.chunks.vis_surface_chunk import VisSurfaceChunk
from io_soulworker.chunks.vis_vertices_material_chunk import VisVerticesMaterialChunk
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_file import VisChunkFileReader


class ModelFileReader(VisChunkFileReader):

    def on_surface(self, _: VisSurfaceChunk): debug('Not impl callback')
    def on_mesh(self, _: VisMeshChunk): debug('Not impl callback')
    def on_skeleton(self): debug('Not impl callback')
    def on_skeleton_weights(self): debug('Not impl callback')

    def on_vertices_material(
        self, _: VisVerticesMaterialChunk): debug('Not impl callback')

    def on_chunk_start(self, cid: VisChunkId, reader: BinaryReader) -> None:
        if cid == VisChunkId.MTRS:
            self.__parse_materials(reader)

        elif cid == VisChunkId.VMSH:
            self.__parse_mesh(cid, reader)

        elif cid == VisChunkId.SKEL:
            self.on_skeleton()

        elif cid == VisChunkId.WGHT:
            self.on_skeleton_weights()

        elif cid == VisChunkId.SUBM:
            self.__parse_vertices_materials(reader)

    def __parse_vertices_materials(self, reader: BinaryReader):

        self.u1 = reader.read_int32()
        self.u2 = reader.read_int32()
        self.u3 = reader.read_int32()

        count = reader.read_uint32()

        for _ in range(count):
            chunk = VisVerticesMaterialChunk(reader)
            self.on_vertices_material(chunk)

    def __parse_mesh(self, cid: VisChunkId, reader: BinaryReader):
        self.on_mesh(VisMeshChunk(cid, reader))

    def __parse_materials(self, reader: BinaryReader):
        count = reader.read_uint32()

        for _ in range(count):
            chunk = VisSurfaceChunk(reader)
            self.on_surface(chunk)
