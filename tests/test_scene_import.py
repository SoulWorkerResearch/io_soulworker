from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import SkipTest, TestCase


def _require_blender() -> None:
    try:
        from io_soulworker.file_import.runner import in_blender
    except ImportError as exc:
        raise SkipTest("requires Blender") from exc

    if not in_blender():
        raise SkipTest("requires Blender")


class TestSceneEntityAnimation(TestCase):
    """Scene entities that repeat a model and play the same ``.anim``."""

    ANIM = Path("Test.anim")

    @classmethod
    def setUpClass(cls) -> None:
        _require_blender()

    def setUp(self) -> None:
        import bpy

        bpy.ops.wm.read_factory_settings(use_empty=True)

        self.skeleton = self._skeleton(["Root", "Arm"])

    def tearDown(self) -> None:
        import bpy

        bpy.ops.wm.read_factory_settings(use_empty=True)

    @staticmethod
    def _skeleton(names: list[str]):
        from mathutils import Matrix, Quaternion, Vector
        from io_soulworker.chunks.skel_chunk import (
            VisSkeletalBone_cl, VisSkeletonChunk_cl,
        )

        skeleton = VisSkeletonChunk_cl()
        world = Matrix.Identity(4)

        for index, name in enumerate(names):
            position = (0.0, 0.0, 0.0) if index == 0 else (20.0, 0.0, 0.0)
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
            skeleton.bones.append(bone)

        return skeleton

    def _entity(self, name: str, skeleton=None):
        """A mesh object skinned to a new armature, like a scene entity."""
        import bpy
        from io_soulworker.file_import.armature_builder import (
            build_armature_from_skeleton,
        )

        skeleton = skeleton or self.skeleton
        rig = build_armature_from_skeleton(bpy.context, name, skeleton).object
        mesh_object = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        bpy.context.collection.objects.link(mesh_object)
        mesh_object.modifiers.new("Armature", "ARMATURE").object = rig

        return mesh_object, rig

    def _reader(self, mesh_object, skeleton=None, *, reuse: bool = False):
        import bpy
        from io_soulworker.file_import.animation.file_reader import (
            AnimationFileReader,
        )

        skeleton = skeleton or self.skeleton
        reader = AnimationFileReader(
            self.ANIM,
            bpy.context,
            target_object=mesh_object,
            reuse_imported_actions=reuse,
        )
        reader.skeletons = [skeleton]
        reader.bone_count = len(skeleton.bones)

        return reader

    def _import(self, mesh_object, names: list[str], skeleton=None) -> None:
        """Feed the reader the sequences a ``.anim`` with these names holds."""
        from mathutils import Vector

        reader = self._reader(mesh_object, skeleton)

        for name in names:
            reader.on_animation(0, name)
            reader.on_bone_position(SimpleNamespace(key_frame_list=[
                SimpleNamespace(time=time, vector_list=[
                    Vector((0.0, 0.0, 0.0)), Vector((20.0 + time, 0.0, 0.0))])
                for time in (0.0, 1.0)
            ]))
            reader.on_animation_end()

    def _arm_travel(self, rig) -> float:
        """How far the animation moves the arm bone at the clip's last frame."""
        import bpy

        bpy.context.scene.frame_set(1)
        bpy.context.scene.frame_set(34)

        return rig.pose.bones["Arm"].location.length

    def test_entities_sharing_an_anim_each_keep_an_animation(self) -> None:
        import bpy

        first, first_rig = self._entity("First")
        second, second_rig = self._entity("Second")

        self._import(first, ["Idle"])
        self._import(second, ["Idle"])

        self.assertEqual(first_rig.animation_data.action.name, "Test:Idle")
        self.assertIsNotNone(second_rig.animation_data.action)
        self.assertNotEqual(
            first_rig.animation_data.action, second_rig.animation_data.action)
        self.assertEqual(len(bpy.data.actions), 2)
        self.assertGreater(self._arm_travel(first_rig), 1e-4)
        self.assertGreater(self._arm_travel(second_rig), 1e-4)

    def test_armatures_with_the_same_skeleton_share_the_imported_actions(
            self) -> None:
        import bpy

        first, first_rig = self._entity("First")
        second, second_rig = self._entity("Second")
        self._import(first, ["Idle", "Run"])

        reused = self._reader(second, reuse=True)._reuse_imported_actions()

        self.assertTrue(reused)
        self.assertEqual(len(bpy.data.actions), 2)
        self.assertEqual(
            second_rig.animation_data.action, first_rig.animation_data.action)
        self.assertEqual(second_rig.animation_data.action.name, "Test:Run")
        self.assertGreater(self._arm_travel(second_rig), 1e-4)
        self.assertGreater(self._arm_travel(first_rig), 1e-4)

    def test_armatures_with_another_skeleton_get_their_own_actions(
            self) -> None:
        import bpy

        other_skeleton = self._skeleton(["Root", "Arm", "Hand"])
        first, first_rig = self._entity("First")
        second, second_rig = self._entity("Second", other_skeleton)
        self._import(first, ["Idle"])

        reused = self._reader(
            second, other_skeleton, reuse=True)._reuse_imported_actions()
        self._import(second, ["Idle"], other_skeleton)

        self.assertFalse(reused)
        self.assertEqual(first_rig.animation_data.action.name, "Test:Idle")
        self.assertEqual(
            second_rig.animation_data.action.name, "Test:Idle@Second_Armature")
        self.assertEqual(len(bpy.data.actions), 2)
        self.assertGreater(self._arm_travel(first_rig), 1e-4)
        self.assertGreater(self._arm_travel(second_rig), 1e-4)

    def test_importing_again_for_an_armature_keeps_actions_others_play(
            self) -> None:
        import bpy

        first, first_rig = self._entity("First")
        second, second_rig = self._entity("Second")
        self._import(first, ["Idle"])
        self._reader(second, reuse=True)._reuse_imported_actions()
        shared = second_rig.animation_data.action

        self._import(first, ["Idle"])
        names = sorted(action.name for action in bpy.data.actions)
        self._import(first, ["Idle"])

        self.assertEqual(second_rig.animation_data.action, shared)
        self.assertNotEqual(first_rig.animation_data.action, shared)
        self.assertEqual(len(names), 2)
        self.assertEqual(
            sorted(action.name for action in bpy.data.actions), names)
        self.assertFalse(any("." in name.rsplit(":", 1)[-1] for name in names))
        self.assertGreater(self._arm_travel(second_rig), 1e-4)
        self.assertGreater(self._arm_travel(first_rig), 1e-4)

    def test_preferred_action_is_picked_among_the_imported_ones_only(
            self) -> None:
        import bpy
        from io_soulworker.file_import.scene.importer import SceneImporter

        by_hand = bpy.data.actions.new("Test:Run")
        entity, rig = self._entity("First")
        self._import(entity, ["Idle", "Run"])
        importer = SceneImporter.__new__(SceneImporter)

        importer._apply_preferred_action(entity, self.ANIM, "Run")

        self.assertNotEqual(rig.animation_data.action, by_hand)
        self.assertEqual(rig.animation_data.action["soulworker_sequence"], "Run")

        importer._apply_preferred_action(entity, self.ANIM, "Idle")

        self.assertEqual(rig.animation_data.action["soulworker_sequence"], "Idle")

    def test_preferred_action_falls_back_to_the_only_imported_sequence(
            self) -> None:
        import bpy
        from io_soulworker.file_import.scene.importer import SceneImporter

        by_hand = bpy.data.actions.new("Test:Walk")
        entity, rig = self._entity("First")
        self._import(entity, ["Idle"])
        importer = SceneImporter.__new__(SceneImporter)

        importer._apply_preferred_action(entity, self.ANIM, "Walk")

        self.assertNotEqual(rig.animation_data.action, by_hand)
        self.assertEqual(rig.animation_data.action["soulworker_sequence"], "Idle")

    def test_preferred_action_of_an_entity_with_shared_actions(self) -> None:
        from io_soulworker.file_import.scene.importer import SceneImporter

        first, first_rig = self._entity("First")
        second, second_rig = self._entity("Second")
        self._import(first, ["Idle", "Run"])
        self._reader(second, reuse=True)._reuse_imported_actions()
        importer = SceneImporter.__new__(SceneImporter)

        importer._apply_preferred_action(second, self.ANIM, "Idle")

        self.assertEqual(second_rig.animation_data.action.name, "Test:Idle")
        self.assertEqual(first_rig.animation_data.action.name, "Test:Run")


class TestLightSerialization(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        _require_blender()

    @staticmethod
    def _string(value: str) -> bytes:
        import struct

        raw = value.encode("cp949")

        return struct.pack("<i", len(raw)) + raw

    def _payload(self) -> bytes:
        """A version 8 light in an archive of version 30, field by field."""
        import struct

        vis_vector = struct.Struct("<4f")
        parts = [
            # VisObject3D: typed-object version, local version, unique id,
            # position, orientation, local orientation, scale, leftover,
            # object key, flags (no rotation matrix), null parent, no vis data.
            struct.pack("<BBq", 0, 5, 77),
            vis_vector.pack(1000.0, 2000.0, 3000.0, 0.0),
            vis_vector.pack(30.0, 40.0, 50.0, 0.0),
            vis_vector.pack(0.0, 0.0, 0.0, 0.0),
            vis_vector.pack(1.0, 1.0, 1.0, 0.0),
            vis_vector.pack(0.0, 0.0, 0.0, 0.0),
            self._string("CapsuleLight_08"),
            struct.pack("<IIB", 0x20, 0, 0),
            # VisLightSource_cl.
            struct.pack("<B", 8),
            struct.pack("<f", 400.0),
            struct.pack("<iH", 0, 0),
            struct.pack("<iBB", 0, 1, 0),
            struct.pack("<i", 5),
            struct.pack("<4B", 0x10, 0x80, 0xF0, 0xFF),
            struct.pack("<2f", 60.0, 60.0),
            self._string(r"World\Textures\Spot.dds"),
            struct.pack("<I", 0xFFFFFFFF),
            struct.pack("<i", 16),
            struct.pack("<4B", 0x10, 0x80, 0xF0, 0xFF),
            struct.pack("<H", 0),
            struct.pack("<II", 0xFFFFFFFD, 0xFF),
            struct.pack("<B", 0),
            struct.pack("<i", 1),
            struct.pack("<f", 0.75),
            self._string(r"Atten\smooth.dds"),
            struct.pack("<i", 0),
            struct.pack("<I", 0xFFFFFFFF),
            struct.pack("<2f", 50.0, 600.0),
            struct.pack("<B", 1),
        ]

        return b"".join(parts)

    def test_light_fields_are_read_from_the_archive_layout(self) -> None:
        from io_soulworker.core.varchive.objects import LightSource
        from io_soulworker.core.varchive.reader import VArchiveReader
        from io_soulworker.core.varchive.registry import build_serializers
        from io_soulworker.core.varchive.serializers import (
            serialize_light_source,
        )

        data = self._payload()
        ar = VArchiveReader(
            data,
            loading_version=30,
            use_object_lengths=False,
            has_per_object_range=False,
            serializers=build_serializers(),
        )
        light = LightSource()
        serialize_light_source(ar, light)

        self.assertTrue(ar.eof())
        self.assertEqual(tuple(light.position), (1000.0, 2000.0, 3000.0))
        self.assertEqual(tuple(light.orientation), (30.0, 40.0, 50.0))
        self.assertEqual(light.object_key, "CapsuleLight_08")
        self.assertEqual(light.light_type, LightSource.TYPE_SPOTLIGHT)
        self.assertEqual(light.radius, 400.0)
        self.assertEqual(light.multiplier, 0.75)
        self.assertEqual(light.rgb, (0x10, 0x80, 0xF0))
        self.assertEqual(light.spot_angle, 60.0)
        self.assertEqual(light.projected_texture, r"World\Textures\Spot.dds")
        self.assertEqual(light.attenuation_texture, r"Atten\smooth.dds")
        self.assertEqual(light.visible_mask, 0xFFFFFFFF)
        self.assertEqual(light.world_influence_mask, 0xFFFFFFFD)
        self.assertEqual(light.object_influence_mask, 0xFF)
        self.assertEqual((light.fade_start, light.fade_end), (50.0, 600.0))
        self.assertEqual(light.flags, 16)
        self.assertTrue(light.cast_shadows)
