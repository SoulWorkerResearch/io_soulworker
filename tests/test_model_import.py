from __future__ import annotations

from os import getenv, stat, utime
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase

import bpy

from io_soulworker.file_import.model.file_reader import (
    ModelFileReader,
    clear_mesh_cache,
)
from io_soulworker.file_import.runner import in_blender


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_STATIC_MODEL = Path("tests/datas/Models/Primitive_Box.model")
_OTHER_STATIC_MODEL = Path("tests/datas/Models/Primitive_Cylinder.model")


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
