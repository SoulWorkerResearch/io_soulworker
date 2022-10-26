from collections import abc
from io_soulworker.chunks.vis_surface_chunk import VisSurfaceChunk

from io_soulworker.core.binary_reader import BinaryReader


# def read_materials(reader: BinaryReader):
#     for _ in range(reader.read_uint32()):
#         yield VisSurfaceChunk(reader)


def indices_to_face(indices: list[int], vertices_per_face=3):
    for offset in range(0, len(indices), vertices_per_face):
        yield indices[offset: offset + vertices_per_face]

    # return map(lambda id: indices[id: id + vertices_per_face], iterator)

# https://youtu.be/2N4tXf3Ensw
