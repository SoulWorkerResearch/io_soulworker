from __future__ import annotations

import sys
from os.path import normpath
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase

import bpy

from io_soulworker.file_export.mesh_builder import (
    build_geometry,
    build_material_sidecars,
)
from io_soulworker.file_export.model_exporter import (
    build_model_from_blender_object,
)
from io_soulworker.file_import.runner import in_blender


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)


_scanned_directories: list[str] = []
_watched_directory: list[str] = []


def _count_directory_scans(event, args):
    """Audit hook: note every listing of the watched directory."""

    if event in ("os.scandir", "os.listdir") and _watched_directory and args:

        if normpath(str(args[0])) == _watched_directory[0]:

            _scanned_directories.append(event)


sys.addaudithook(_count_directory_scans)


class TestExportGeometry(TestCase):

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def tearDown(self) -> None:

        _watched_directory.clear()
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _link(self, name: str, vertices, faces):

        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        return obj

    def test_polygon_material_index_decides_the_exported_surface(self):

        obj = self._link(
            "Split",
            [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
             (2, 0, 0), (3, 0, 0), (3, 1, 0), (2, 1, 0)],
            [(0, 1, 2, 3), (4, 5, 6, 7)],
        )

        for name in ("First", "Second"):

            obj.data.materials.append(bpy.data.materials.new(name))

        # What the importer leaves behind: one group per material holding the
        # vertices of that sub-mesh, next to the matching material_index.
        obj.vertex_groups.new(name="First").add([0, 1, 2, 3], 1.0, "REPLACE")
        obj.vertex_groups.new(name="Second").add([4, 5, 6, 7], 1.0, "REPLACE")
        obj.data.polygons[1].material_index = 1

        split = build_geometry(obj).sub_meshes.meshes

        self.assertEqual([buffer.surface_index for buffer in split], [0, 1])

        # The user moves the first quad to the second material in Edit mode.
        obj.data.polygons[0].material_index = 1

        moved = build_geometry(obj).sub_meshes.meshes

        self.assertEqual([buffer.surface_index for buffer in moved], [1])
        self.assertEqual(moved[0].indices_count, 12)

    def test_vertices_with_different_weights_are_not_merged(self):

        obj = self._link(
            "Weighted",
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 0), (1, 0, 0)],
            [(0, 1, 2), (3, 4, 2)],
        )

        # Vertex 3 sits on vertex 0 and vertex 4 on vertex 1, with the same
        # normal and UV. Only vertex 3 is skinned to another bone.
        rig_data = bpy.data.armatures.new("WeightedRig")
        rig = bpy.data.objects.new("WeightedRig", rig_data)
        bpy.context.collection.objects.link(rig)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")

        for index, name in enumerate(("Root", "Other")):

            bone = rig_data.edit_bones.new(name)
            bone.head = (0.0, 0.0, 0.1 * index)
            bone.tail = (0.0, 0.0, 0.1 * index + 0.05)

        bpy.ops.object.mode_set(mode="OBJECT")
        rig["soulworker_bone_names_by_index"] = ["Root", "Other"]

        obj.vertex_groups.new(name="Root").add([0, 1, 2, 4], 1.0, "REPLACE")
        obj.vertex_groups.new(name="Other").add([3], 1.0, "REPLACE")

        data = build_model_from_blender_object(obj, rig)

        # Vertex 4 shares its weights with vertex 1, so only vertex 3 splits.
        self.assertEqual(len(data.mesh.vertices), 4)
        self.assertEqual(len(data.weights), 4)

        bones_at_origin = sorted(
            entity.bone_index
            for position, weight in zip(data.mesh.vertices, data.weights)
            if position.length < 1e-6
            for entity in weight.values
        )

        self.assertEqual(bones_at_origin, [0, 1])

    def test_missing_textures_scan_the_resource_tree_once(self):

        obj = self._link(
            "Textured",
            [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            [(0, 1, 2)],
        )

        for index in range(3):

            material = bpy.data.materials.new(f"Skin{index}")
            # The author's own tree, absent from the unpacked game data:
            # the file can only be found by its name.
            material["soulworker_diffuse"] = (
                rf"\_Graphic\Hero\unique_{index}.dds")
            material["soulworker_specular"] = r"\_Graphic\Hero\twice.dds"
            material["soulworker_normal"] = r"\_Graphic\Hero\nowhere.dds"
            obj.data.materials.append(material)

        with TemporaryDirectory() as folder:

            root = Path(folder) / "unpacked"

            for relative in (
                    "Deep/Down/unique_0.dds", "Deep/Down/unique_1.dds",
                    "Elsewhere/unique_2.dds", "Left/twice.dds",
                    "Right/twice.dds", "Unrelated/Marker/other.dds"):

                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_bytes(b"")

            _scanned_directories.clear()
            _watched_directory[:] = [normpath(str(root / "Unrelated/Marker"))]

            sidecars = build_material_sidecars(obj, root)

            _watched_directory.clear()

            self.assertEqual(len(sidecars), 3)
            # A name that exactly one file carries is recovered ...
            self.assertEqual(
                [Path(sidecar.diffuse).resolve() for sidecar in sidecars],
                [(root / "Deep/Down/unique_0.dds").resolve(),
                 (root / "Deep/Down/unique_1.dds").resolve(),
                 (root / "Elsewhere/unique_2.dds").resolve()],
            )

            for sidecar in sidecars:

                # ... a name carried by two files, or by none, is kept as is.
                self.assertEqual(sidecar.specular, r"\_Graphic\Hero\twice.dds")
                self.assertEqual(sidecar.normal, r"\_Graphic\Hero\nowhere.dds")

            self.assertLessEqual(len(_scanned_directories), 1)
