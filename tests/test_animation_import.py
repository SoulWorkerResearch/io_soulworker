from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import SkipTest, TestCase


class TestAnimationImport(TestCase):
    """Imported clips, driven through the reader without game files."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from io_soulworker.file_import.runner import in_blender
        except ImportError as exc:
            raise SkipTest("requires Blender") from exc

        if not in_blender():
            raise SkipTest("requires Blender")

    def setUp(self) -> None:
        import bpy
        from mathutils import Matrix, Quaternion, Vector
        from io_soulworker.chunks.skel_chunk import (
            VisSkeletalBone_cl, VisSkeletonChunk_cl,
        )
        from io_soulworker.file_import.armature_builder import (
            build_armature_from_skeleton,
        )

        bpy.ops.wm.read_factory_settings(use_empty=True)

        self.skeleton = VisSkeletonChunk_cl()
        world = Matrix.Identity(4)
        for index, (name, position) in enumerate([
            ("Root", (0.0, 0.0, 0.0)),
            ("Arm", (20.0, 0.0, 0.0)),
        ]):
            bone = VisSkeletalBone_cl()
            bone.id = index
            bone.name = name
            bone.parent_id = index - 1
            bone.local_space_position = Vector(position)
            bone.local_space_orientation = Quaternion()
            world = world @ Matrix.Translation(position)
            inverse = world.inverted()
            bone.inverse_object_space_position = inverse.translation
            bone.inverse_object_space_orientation = inverse.to_quaternion()
            self.skeleton.bones.append(bone)

        rig = build_armature_from_skeleton(
            bpy.context, "Test", self.skeleton).object
        self.mesh_object = bpy.data.objects.new(
            "Test", bpy.data.meshes.new("Test"))
        bpy.context.collection.objects.link(self.mesh_object)
        self.mesh_object.modifiers.new("Armature", "ARMATURE").object = rig
        self.rig = rig

    def tearDown(self) -> None:
        import bpy

        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _import_sequences(
            self, path: Path, names: list[str], report_warning=None) -> None:
        """Feed one reader the sequences a ``.anim`` with these names holds."""
        import bpy
        from mathutils import Vector
        from io_soulworker.file_import.animation.file_reader import (
            AnimationFileReader,
        )

        reader = AnimationFileReader(
            path,
            bpy.context,
            target_object=self.mesh_object,
            report_warning=report_warning,
        )
        reader.skeletons = [self.skeleton]
        reader.bone_count = 2

        for name in names:
            reader.on_animation(0, name)
            reader.on_bone_position(SimpleNamespace(key_frame_list=[
                SimpleNamespace(time=time, vector_list=[
                    Vector((0.0, 0.0, 0.0)), Vector((20.0 + time, 0.0, 0.0))])
                for time in (0.0, 1.0)
            ]))
            reader.on_animation_end()

    def test_every_imported_action_survives_saving_the_file(self) -> None:
        import bpy

        self._import_sequences(Path("Test.anim"), ["Idle", "Run", "Jump"])

        with TemporaryDirectory() as folder:
            blend = str(Path(folder) / "saved.blend")
            bpy.ops.wm.save_as_mainfile(filepath=blend, check_existing=False)
            bpy.ops.wm.open_mainfile(filepath=blend)

        self.assertEqual(
            sorted(action.name for action in bpy.data.actions),
            ["Test:Idle", "Test:Jump", "Test:Run"],
        )
        self.assertEqual(
            bpy.data.objects["Test_Armature"].animation_data.action.name,
            "Test:Jump",
        )

    def test_import_sets_the_scene_to_the_animation_frame_rate(self) -> None:
        import bpy

        render = bpy.context.scene.render
        render.fps = 24
        render.fps_base = 1.0
        messages: list[str] = []

        self._import_sequences(
            Path("Test.anim"), ["Idle", "Run"], messages.append)

        self.assertEqual((render.fps, render.fps_base), (33, 1.0))
        self.assertEqual(len(messages), 1)
        self.assertIn("24", messages[0])
        self.assertIn("33", messages[0])

        messages.clear()
        self._import_sequences(Path("Test.anim"), ["Idle"], messages.append)

        self.assertEqual(messages, [])
