from __future__ import annotations

from io import BytesIO
from pathlib import Path
from struct import unpack_from
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase
from unittest.mock import patch

import bpy
import bmesh
from mathutils import Vector

from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.vertex_layout import LAYOUT_PROPERTY
from io_soulworker.core.vis_vertex_descriptor import VisMBVertexDescriptor_cl
from io_soulworker.file_export import vmesh_exporter
from io_soulworker.file_export.mesh_builder import build_geometry
from io_soulworker.file_export.vertex_channels import VertexChannels
from io_soulworker.file_import.model.chunk_reader import ModelChunkReader
from io_soulworker.file_import.model.file_reader import (
    ModelFileReader,
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


class _MeshGrabber(ModelChunkReader):
    """Parse a file and keep the mesh chunk."""

    def __init__(self, path: Path) -> None:

        super().__init__(path)
        self.chunk = None

    def on_mesh(self, chunk) -> None:

        self.chunk = chunk

    def on_chunk_start(self, scope, reader) -> None:

        if scope.depth >= 0:

            super().on_chunk_start(scope, reader)


def _parse(path: Path):

    grabber = _MeshGrabber(path)
    grabber.run()

    return grabber.chunk


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

    def setUp(self) -> None:

        clear_mesh_cache()

    def tearDown(self) -> None:

        clear_mesh_cache()
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _write_quad(self, folder: str, edit, name: str = "Quad.vmesh") -> Path:
        """Write a four vertex file whose mesh chunk ``edit`` has changed."""

        source = _quad_object()
        data = vmesh_exporter.build_vmesh_from_blender_object(source)
        edit(data.mesh)
        path = Path(folder) / name

        with patch.object(vmesh_exporter, "build_vmesh_from_blender_object",
                          return_value=data):
            vmesh_exporter.write_vmesh_file(path, source)

        return path

    @staticmethod
    def _make_rich(chunk) -> None:

        chunk.descriptor = _rich_descriptor()
        chunk.uvs = [Vector((u, -v)) for u, v in _UV0]
        chunk.colors = list(_COLORS)
        chunk.tex_sets = {
            1: list(_LIGHTMAP), 2: list(_VECTORS), 5: list(_WIDE)}

    @staticmethod
    def _make_opaque(chunk) -> None:

        chunk.descriptor = _opaque_descriptor()
        chunk.uvs = [Vector((u, -v)) for u, v in _UV0]
        chunk.opaque = {"tex3": [bytes([i, 2, 3, 4]) for i in range(4)]}

    def _import(self, path: Path):

        return ModelFileReader(path, bpy.context, 7.0, reuse_mesh=False).run()

    def _export(self, obj, folder: str, name: str = "Out.vmesh"):

        path = Path(folder) / name
        vmesh_exporter.write_vmesh_file(path, obj)

        return _parse(path)

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

    def test_every_two_float_set_becomes_a_uv_layer_in_slot_order(self):

        with TemporaryDirectory() as folder:

            obj = self._import(self._write_quad(folder, self._make_rich))

        mesh = obj.data

        self.assertEqual(
            [layer.name for layer in mesh.uv_layers],
            ["UVMap", "UVMap_1", "UVMap_5"])
        self.assertEqual(mesh.uv_layers.active.name, "UVMap")
        self.assertTrue(mesh.uv_layers["UVMap"].active_render)

        vectors = mesh.attributes["sw_tex2"]

        self.assertEqual((vectors.domain, vectors.data_type),
                         ("POINT", "FLOAT_VECTOR"))
        self.assertEqual(
            [tuple(round(c, 6) for c in item.vector) for item in vectors.data],
            _VECTORS)

        color = mesh.color_attributes[0]

        self.assertEqual((color.domain, color.data_type),
                         ("POINT", "FLOAT_COLOR"))
        self.assertEqual(
            [tuple(round(c * 255) for c in item.color) for item in color.data],
            _COLORS)

    def test_first_set_keeps_v_negated_and_later_sets_land_in_the_unit_square(self):

        with TemporaryDirectory() as folder:

            obj = self._import(self._write_quad(folder, self._make_rich))

        mesh = obj.data
        corner = {loop.vertex_index: loop.index for loop in mesh.loops}

        for vertex, (u, v) in enumerate(_UV0):

            first = mesh.uv_layers["UVMap"].uv[corner[vertex]].vector
            self.assertAlmostEqual(first[1], -v, places=6)

        for vertex, (u, v) in enumerate(_LIGHTMAP):

            second = mesh.uv_layers["UVMap_1"].uv[corner[vertex]].vector
            self.assertAlmostEqual(second[0], u, places=6)
            self.assertAlmostEqual(second[1], 1.0 - v, places=6)
            self.assertTrue(0.0 <= second[1] <= 1.0)

    def test_imported_mesh_exports_the_layout_it_arrived_with(self):

        with TemporaryDirectory() as folder:

            path = self._write_quad(folder, self._make_rich)
            original = _parse(path)
            exported = self._export(self._import(path), folder)

        self.assertEqual(exported.descriptor.to_record(),
                         original.descriptor.to_record())
        self.assertEqual(exported.vertex_count, original.vertex_count)
        self.assertEqual(exported.colors, original.colors)

        for slot, values in original.tex_sets.items():

            for before, after in zip(values, exported.tex_sets[slot]):

                for a, b in zip(before, after):

                    self.assertAlmostEqual(a, b, places=6)

        for before, after in zip(original.uvs, exported.uvs):

            self.assertAlmostEqual(before.x, after.x, places=6)
            self.assertAlmostEqual(before.y, after.y, places=6)

    def test_field_the_mesh_lost_is_dropped_and_the_rest_packed(self):

        with TemporaryDirectory() as folder:

            obj = self._import(self._write_quad(folder, self._make_rich))
            mesh = obj.data
            mesh.uv_layers.remove(mesh.uv_layers["UVMap_1"])

            with self.assertLogs(level="WARNING") as logs:

                exported = self._export(obj, folder)

        self.assertIn("tex1", "\n".join(logs.output))

        descriptor = exported.descriptor

        self.assertEqual(descriptor.stride, 56)
        self.assertEqual(descriptor.color_offset, 0x0018)
        self.assertEqual(descriptor.tex_offset[0], 0x201C)
        self.assertEqual(descriptor.tex_offset[1], descriptor.UNSET_OFFSET)
        self.assertEqual(descriptor.tex_offset[2], 0x3024)
        self.assertEqual(descriptor.tex_offset[5], 0x2030)
        self.assertEqual(exported.colors, _COLORS)
        self.assertEqual([tuple(round(c, 6) for c in v)
                          for v in exported.tex_sets[2]], _VECTORS)

    def test_bytes_of_an_undecoded_field_come_back_while_the_vertex_count_is_unchanged(self):

        with TemporaryDirectory() as folder:

            path = self._write_quad(folder, self._make_opaque)
            original = _parse(path)
            exported = self._export(self._import(path), folder)

        self.assertEqual(original.opaque["tex3"][1], bytes([1, 2, 3, 4]))
        self.assertEqual(exported.descriptor.to_record(),
                         original.descriptor.to_record())
        self.assertEqual(exported.opaque, original.opaque)

    def test_undecoded_field_is_dropped_when_the_vertex_count_changed(self):

        with TemporaryDirectory() as folder:

            obj = self._import(self._write_quad(folder, self._make_opaque))
            editor = bmesh.new()
            editor.from_mesh(obj.data)
            editor.verts.new((5.0, 5.0, 5.0))
            editor.to_mesh(obj.data)
            editor.free()

            with self.assertLogs(level="WARNING") as logs:

                exported = self._export(obj, folder)

        self.assertIn("tex3", "\n".join(logs.output))
        self.assertEqual(exported.opaque, {})
        self.assertEqual(exported.descriptor.stride, 32)
        self.assertEqual(exported.descriptor.tex_offset[3],
                         exported.descriptor.UNSET_OFFSET)

    def test_unreadable_layout_record_is_ignored(self):

        obj = _quad_object()
        obj.data[LAYOUT_PROPERTY] = "{not json"

        with self.assertLogs(level="WARNING"):

            descriptor = build_geometry(obj).mesh.descriptor

        self.assertEqual(descriptor.stride, 32)

    def test_mesh_made_in_blender_keeps_the_plain_layout(self):

        descriptor = build_geometry(_quad_object()).mesh.descriptor

        self.assertEqual(descriptor.stride, 32)
        self.assertEqual(descriptor.pos_offset, 0x3000)
        self.assertEqual(descriptor.normal_offset, 0x300C)
        self.assertEqual(descriptor.tex_offset[0], 0x2018)
        self.assertEqual(descriptor.color_offset, descriptor.UNSET_OFFSET)
        self.assertEqual(descriptor.tex_offset[1], descriptor.UNSET_OFFSET)

    def test_mesh_made_in_blender_adds_extra_uv_layers_and_the_colour(self):

        obj = _quad_object()
        mesh = obj.data

        for name in ("Base", "Lightmap"):

            layer = mesh.uv_layers.new(name=name)
            layer.uv.foreach_set("vector", [0.0] * (2 * len(mesh.loops)))

        color = mesh.color_attributes.new("Col", "BYTE_COLOR", "POINT")
        color.data.foreach_set(
            "color_srgb", [c / 255.0 for item in _COLORS for c in item])

        geometry = build_geometry(obj)
        descriptor = geometry.mesh.descriptor

        self.assertEqual(descriptor.stride, 44)
        self.assertEqual(descriptor.color_offset, 0x0018)
        self.assertEqual(descriptor.tex_offset[0], 0x201C)
        self.assertEqual(descriptor.tex_offset[1], 0x2024)
        self.assertEqual(
            [geometry.mesh.colors[i] for i in range(4)], _COLORS)
        self.assertEqual(len(geometry.mesh.tex_sets[1]), 4)

    def test_vertex_key_treats_nan_as_equal(self):

        nan = float("nan")

        self.assertEqual(VertexChannels.key(((nan, 0.5),)),
                         VertexChannels.key(((nan, 0.5),)))
        self.assertNotEqual(VertexChannels.key(((nan, 0.5),)),
                            VertexChannels.key(((0.0, 0.5),)))
