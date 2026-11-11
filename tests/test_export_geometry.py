from __future__ import annotations

from unittest import SkipTest, TestCase

import bpy

from io_soulworker.file_export.mesh_builder import build_geometry
from io_soulworker.file_export.model_exporter import (
    build_model_from_blender_object,
)
from io_soulworker.file_import.runner import in_blender


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)


class TestExportGeometry(TestCase):

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def tearDown(self) -> None:

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
