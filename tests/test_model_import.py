from __future__ import annotations

from os import getenv, stat, utime
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import SkipTest, TestCase
from unittest.mock import patch

import bpy
from mathutils import Vector

from io_soulworker.file_export import vmesh_exporter
from io_soulworker.file_import.model.file_reader import (
    ModelFileReader,
    clear_mesh_cache,
)
from io_soulworker.file_import.object_panel_default_values import (
    FileImportObjectPanelDefaultValues,
)
from io_soulworker.file_import.object_panel_features import (
    FileImportObjectPanelFeatures,
)
from io_soulworker.file_import.runner import (
    FileImportRunner,
    in_blender,
    is_import_operator,
)


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_STATIC_MODEL = Path("tests/datas/Models/Primitive_Box.model")
_OTHER_STATIC_MODEL = Path("tests/datas/Models/Primitive_Cylinder.model")


# Six shared vertices in a strip. The faces come in two sub-meshes: surface 0
# owns the first three entries (one of them degenerate, so validation drops it)
# and surface 1 the last two. Face (2, 3, 4) of surface 0 uses only vertices
# that surface 1 also uses.
_SHARED_VERTICES = [(0, 0, 0), (1, 0, 0), (0, 1, 0),
                    (1, 1, 0), (0, 2, 0), (1, 2, 0)]
_SHARED_FACES = [(0, 1, 2), (1, 1, 3), (2, 3, 4), (1, 2, 3), (3, 4, 5)]
_SURFACE_FACE_COUNTS = [3, 2]


class TestModelImport(TestCase):

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def setUp(self) -> None:

        clear_mesh_cache()

    def tearDown(self) -> None:

        clear_mesh_cache()
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_skinned_model_imported_twice_has_a_skeleton_each_time(self):

        root = Path(getenv(
            'SOULWORKER_RESOURCES',
            'A:/SteamLibrary/steamapps/common/Soulworker_KR/_datas'))
        path = root / 'Character/NPC/NPC_0001_Mirium/NPC_0001_Mirium_Upper.model'
        if not path.is_file():
            self.skipTest('unpacked Mirium model unavailable')

        first = ModelFileReader(path, bpy.context, 7.0).run()
        second = ModelFileReader(path, bpy.context, 7.0).run()

        for imported in (first, second):

            armatures = [
                modifier for modifier in imported.modifiers
                if modifier.type == 'ARMATURE'
            ]

            self.assertIsNotNone(imported.parent)
            self.assertEqual(imported.parent.type, 'ARMATURE')
            self.assertEqual(len(armatures), 1)
            self.assertIs(armatures[0].object, imported.parent)

        self.assertIsNot(first.parent, second.parent)

    def test_static_mesh_is_shared_between_imports(self):

        first = ModelFileReader(_STATIC_MODEL, bpy.context, 7.0).run()
        second = ModelFileReader(_STATIC_MODEL, bpy.context, 7.0).run()

        self.assertIsNot(first, second)
        self.assertIs(first.data, second.data)

    def test_changed_file_is_read_again(self):

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Cached.model"
            copyfile(_STATIC_MODEL, path)

            first = ModelFileReader(path, bpy.context, 7.0).run()
            unchanged = ModelFileReader(path, bpy.context, 7.0).run()

            self.assertIs(first.data, unchanged.data)

            # Same bytes, newer modification time.
            before = stat(path)
            utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 10**9))
            touched = ModelFileReader(path, bpy.context, 7.0).run()

            self.assertIsNot(touched.data, first.data)

            # Other bytes under the modification time the cache has seen.
            before = stat(path)
            copyfile(_OTHER_STATIC_MODEL, path)
            utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            replaced = ModelFileReader(path, bpy.context, 7.0).run()

            self.assertIsNot(replaced.data, touched.data)
            self.assertGreater(len(replaced.data.vertices),
                               len(touched.data.vertices))

    def _write_shared_vertex_model(self, folder: str) -> Path:
        """Write a .vmesh whose sub-meshes share vertices (see ``_SHARED_FACES``)."""

        mesh = bpy.data.meshes.new("Strip")
        mesh.from_pydata(
            _SHARED_VERTICES, [], [(0, 1, 2), (2, 3, 4), (1, 2, 3), (3, 4, 5)])
        mesh.materials.append(bpy.data.materials.new("SurfaceA"))
        mesh.materials.append(bpy.data.materials.new("SurfaceB"))
        mesh.polygons.foreach_set("material_index", [0, 0, 1, 1])
        source = bpy.data.objects.new("Strip", mesh)

        data = vmesh_exporter.build_vmesh_from_blender_object(source)
        data.mesh.vertices = [Vector(vertex) for vertex in _SHARED_VERTICES]
        data.mesh.normals = [Vector((0, 0, 1))] * len(_SHARED_VERTICES)
        data.mesh.uvs = [Vector((0, 0))] * len(_SHARED_VERTICES)
        data.mesh.faces = [list(face) for face in _SHARED_FACES]
        data.mesh.indices = [index for face in _SHARED_FACES for index in face]
        data.mesh.current_prim_count = len(_SHARED_FACES)

        start = 0
        for sub_mesh, faces in zip(data.sub_meshes.meshes, _SURFACE_FACE_COUNTS):
            sub_mesh.indices_start = start
            sub_mesh.indices_count = 3 * faces
            start += 3 * faces

        path = Path(folder) / "Strip.vmesh"
        with patch.object(vmesh_exporter, "build_vmesh_from_blender_object",
                          return_value=data):
            vmesh_exporter.write_vmesh_file(path, source)

        return path

    def test_material_indices_follow_the_sub_mesh_ranges(self):

        with TemporaryDirectory() as folder:

            path = self._write_shared_vertex_model(folder)
            imported = ModelFileReader(
                path, bpy.context, 7.0, reuse_mesh=False).run()

        mesh = imported.data

        self.assertEqual(
            [polygon.material_index for polygon in mesh.polygons], [0, 0, 1, 1])
        self.assertEqual(imported.mode, 'OBJECT')

        # The exporter and older .blend files find a surface by this group.
        self.assertEqual(
            sorted(group.name for group in imported.vertex_groups),
            sorted(material.name for material in mesh.materials))

    def test_material_assignment_does_not_need_the_object_in_the_view_layer(self):

        hidden = bpy.data.collections.new("Hidden")
        bpy.context.scene.collection.children.link(hidden)
        bpy.context.view_layer.layer_collection.children["Hidden"].exclude = True

        with TemporaryDirectory() as folder:

            path = self._write_shared_vertex_model(folder)
            imported = ModelFileReader(
                path, bpy.context, 7.0,
                collection=hidden, reuse_mesh=False).run()

        self.assertEqual(
            [polygon.material_index for polygon in imported.data.polygons],
            [0, 0, 1, 1])

    def test_option_panels_show_only_for_the_import_operator(self):

        running = []

        class Probe(FileImportRunner):

            def execute(self, context):

                running.append((self.bl_idname, is_import_operator(self)))

                return {'FINISHED'}

        bpy.utils.register_class(Probe)
        try:
            getattr(bpy.ops.io_soulworker, "import")()
        finally:
            bpy.utils.unregister_class(Probe)

        # A running operator reports its id the way the file browser sees it.
        self.assertEqual(running, [("IO_SOULWORKER_OT_import", True)])

        def context_with(operator):

            return SimpleNamespace(
                space_data=SimpleNamespace(active_operator=operator))

        other = SimpleNamespace(bl_idname="IMPORT_ANIM_OT_bvh")
        ours = SimpleNamespace(bl_idname=running[0][0])

        for panel in (FileImportObjectPanelDefaultValues,
                      FileImportObjectPanelFeatures):

            self.assertTrue(panel.poll(context_with(ours)))
            self.assertFalse(panel.poll(context_with(other)))
            self.assertFalse(panel.poll(context_with(None)))
            self.assertFalse(panel.poll(SimpleNamespace(space_data=None)))

        # The operator draws nothing itself; the panels draw its options.
        self.assertIn("draw", vars(FileImportRunner))
