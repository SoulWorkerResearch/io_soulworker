from __future__ import annotations

from io import BytesIO
from struct import unpack_from
from unittest import SkipTest, TestCase

import bpy
from mathutils import Vector

from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.vis_vertex_descriptor import VisMBVertexDescriptor_cl
from io_soulworker.file_export import vmesh_exporter
from io_soulworker.file_import.model.file_reader import (
    clear_mesh_cache,
)
from io_soulworker.file_import.runner import in_blender


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_QUAD = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
_QUAD_FACES = [(0, 1, 2), (0, 2, 3)]

# The values the quad carries in the file: the first set has V negated, as
# the chunk holds it; the others are as stored.
_UV0 = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
_LIGHTMAP = [(0.25, 0.75), (0.5, 0.75), (0.5, 1.0), (0.25, 1.0)]
_VECTORS = [(0.5, -0.5, 0.25), (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
_WIDE = [(10.0, 20.0), (11.0, 21.0), (12.0, 22.0), (13.0, 23.0)]
_COLORS = [(255, 0, 0, 255), (0, 255, 0, 128),
           (0, 0, 255, 0), (10, 20, 30, 40)]


def _rich_descriptor() -> VisMBVertexDescriptor_cl:
    """Position, normal, colour, UV sets 0, 1 and 5 and a three-float set 2."""

    descriptor = VisMBVertexDescriptor_cl()
    descriptor.stride = 64
    descriptor.pos_offset = 0x3000
    descriptor.normal_offset = 0x300C
    descriptor.color_offset = 0x0018
    descriptor.tex_offset[0] = 0x201C
    descriptor.tex_offset[1] = 0x2024
    descriptor.tex_offset[2] = 0x302C
    descriptor.tex_offset[5] = 0x2038
    descriptor.first_text_coord = 255

    return descriptor


def _opaque_descriptor() -> VisMBVertexDescriptor_cl:
    """Position, normal, UV set 0 and four bytes of a format nobody decodes."""

    descriptor = VisMBVertexDescriptor_cl()
    descriptor.stride = 36
    descriptor.pos_offset = 0x3000
    descriptor.normal_offset = 0x300C
    descriptor.tex_offset[0] = 0x2018
    descriptor.tex_offset[3] = 0x4020
    descriptor.first_text_coord = 255

    return descriptor


def _quad_object(name: str = "Quad"):

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(_QUAD, [], _QUAD_FACES)
    mesh.update()
    mesh.materials.append(bpy.data.materials.new(name + "Surface"))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    return obj


class TestVertexChannels(TestCase):

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def tearDown(self) -> None:

        clear_mesh_cache()
        bpy.ops.wm.read_factory_settings(use_empty=True)

    @staticmethod
    def _make_rich(chunk) -> None:

        chunk.descriptor = _rich_descriptor()
        chunk.uvs = [Vector((u, -v)) for u, v in _UV0]
        chunk.colors = list(_COLORS)
        chunk.tex_sets = {
            1: list(_LIGHTMAP), 2: list(_VECTORS), 5: list(_WIDE)}

    def test_descriptor_sizes_come_from_format_codes_or_the_gap_to_the_next_field(self):

        descriptor = _opaque_descriptor()
        descriptor.color_offset = 0x0018
        descriptor.tex_offset[0] = 0x201C
        descriptor.tex_offset[3] = 0x4024
        descriptor.stride = 40
        # Starts at the end of the stride: ignored, not read out of bounds.
        descriptor.tex_offset[4] = 0x2028

        with self.assertLogs(level="WARNING"):

            fields = [(f.name, f.offset, f.size, f.known)
                      for f in descriptor.components()]

        self.assertEqual(fields, [
            ("position", 0, 12, True),
            ("normal", 12, 12, True),
            ("color", 24, 4, True),
            ("tex0", 28, 8, True),
            ("tex3", 36, 4, False),
        ])

    def test_chunk_writes_each_field_at_its_offset(self):

        source = _quad_object()
        chunk = vmesh_exporter.build_vmesh_from_blender_object(source).mesh
        self._make_rich(chunk)
        buffer = BytesIO()
        writer = BinaryWriter(buffer)
        chunk.write(writer)
        writer.flush()
        blob = buffer.getvalue()

        stride = chunk.descriptor.stride
        # 16-bit indices, then the bounding box and one more integer.
        tail = 2 * len(chunk.indices) + 24 + 4
        start = len(blob) - tail - stride * 4

        self.assertEqual(stride, 64)
        self.assertEqual(unpack_from("<4B", blob, start + 24), _COLORS[0])
        self.assertEqual(unpack_from("<ff", blob, start + 28), (0.0, -0.0))
        self.assertEqual(unpack_from("<ff", blob, start + 36), _LIGHTMAP[0])
        self.assertEqual(unpack_from("<fff", blob, start + 44), _VECTORS[0])
        self.assertEqual(unpack_from("<ff", blob, start + 56), _WIDE[0])
        self.assertEqual(unpack_from("<4B", blob, start + stride + 24),
                         _COLORS[1])
        self.assertEqual(unpack_from("<ff", blob, start + stride + 28),
                         (1.0, -0.0))
