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


class TestSceneLights(TestCase):
    """Blender lights made from ``VisLightSource_cl`` objects."""

    @classmethod
    def setUpClass(cls) -> None:
        _require_blender()

    def setUp(self) -> None:
        import bpy

        bpy.ops.wm.read_factory_settings(use_empty=True)

        self.collection = bpy.data.collections.new("Zone")
        bpy.context.scene.collection.children.link(self.collection)

    def tearDown(self) -> None:
        import bpy

        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _make(self, **fields):
        """Create a light object for a synthetic ``LightSource``."""
        from io_soulworker.core.varchive.objects import LightSource
        from io_soulworker.file_import.scene.importer import entity_world_matrix
        from io_soulworker.file_import.scene.lights import create_light_object

        light = LightSource()
        light.light_type = LightSource.TYPE_POINT
        light.radius = 400.0

        for name, value in fields.items():
            setattr(light, name, value)

        return create_light_object(
            light, self.collection, entity_world_matrix(light))

    def test_vision_light_types_become_point_sun_and_spot_lights(self) -> None:
        from io_soulworker.core.varchive.objects import LightSource

        point = self._make(light_type=LightSource.TYPE_POINT)
        sun = self._make(light_type=LightSource.TYPE_DIRECTIONAL)
        spot = self._make(light_type=LightSource.TYPE_SPOTLIGHT)

        self.assertEqual(
            (point.data.type, sun.data.type, spot.data.type),
            ("POINT", "SUN", "SPOT"),
        )

    def test_unknown_light_type_creates_nothing(self) -> None:
        import bpy

        self.assertIsNone(self._make(light_type=2))
        self.assertEqual(len(bpy.data.lights), 0)
        self.assertEqual(len(self.collection.objects), 0)

    def test_colour_bytes_are_srgb_and_become_linear(self) -> None:
        from io_soulworker.file_import.scene.lights import srgb_to_linear

        # Bytes r, g, b, a stored as one little-endian uint32.
        obj = self._make(color=0xFF0080FF)

        red, green, blue = obj.data.color

        self.assertAlmostEqual(red, 1.0, places=5)
        self.assertAlmostEqual(green, srgb_to_linear(128 / 255), places=5)
        self.assertAlmostEqual(green, 0.2159, places=3)
        self.assertEqual(blue, 0.0)

    def test_point_light_reaches_as_far_as_its_radius_in_metres(self) -> None:
        from io_soulworker.core.varchive.objects import LightSource

        point = self._make(radius=400.0)
        sun = self._make(light_type=LightSource.TYPE_DIRECTIONAL, radius=1000.0)
        dark = self._make(radius=0.0)

        self.assertTrue(point.data.use_custom_distance)
        self.assertAlmostEqual(point.data.cutoff_distance, 4.0, places=5)
        self.assertFalse(sun.data.use_custom_distance)
        self.assertFalse(dark.data.use_custom_distance)

    def test_power_follows_multiplier_and_radius(self) -> None:
        from math import pi
        from io_soulworker.core.varchive.objects import LightSource

        point = self._make(radius=400.0, multiplier=1.0)
        brighter = self._make(radius=400.0, multiplier=2.0)
        wider = self._make(radius=800.0, multiplier=1.0)
        sun = self._make(
            light_type=LightSource.TYPE_DIRECTIONAL, multiplier=0.3)
        off = self._make(radius=400.0, multiplier=0.0)

        self.assertAlmostEqual(point.data.energy, pi ** 3 * 16.0, places=3)
        self.assertAlmostEqual(
            brighter.data.energy, 2.0 * point.data.energy, places=3)
        self.assertAlmostEqual(
            wider.data.energy, 4.0 * point.data.energy, places=3)
        self.assertAlmostEqual(sun.data.energy, 0.3 * pi, places=5)
        self.assertEqual(off.data.energy, 0.0)

    def test_spot_size_is_the_full_cone_angle_within_blender_limits(
            self) -> None:
        from math import pi, radians
        from io_soulworker.core.varchive.objects import LightSource

        kind = LightSource.TYPE_SPOTLIGHT
        spot = self._make(light_type=kind, spot_angle=90.0)
        narrow = self._make(light_type=kind, spot_angle=0.0)
        wide = self._make(light_type=kind, spot_angle=400.0)
        broken = self._make(light_type=kind, spot_angle=float("nan"))

        self.assertAlmostEqual(spot.data.spot_size, pi / 2, places=5)
        self.assertAlmostEqual(narrow.data.spot_size, radians(1.0), places=5)
        self.assertAlmostEqual(wide.data.spot_size, pi, places=5)
        self.assertAlmostEqual(broken.data.spot_size, pi, places=5)

    def test_light_is_placed_like_an_entity_and_shines_along_vision_y(
            self) -> None:
        from mathutils import Vector

        def direction(obj) -> Vector:
            return obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))

        placed = self._make(
            position=Vector((100.0, 200.0, 300.0)),
            orientation=Vector((0.0, 90.0, 0.0)),
        )
        turned = self._make(orientation=Vector((90.0, 0.0, 0.0)))

        self.assertAlmostEqual((placed.location - Vector((1, 2, 3))).length, 0)
        self.assertAlmostEqual(
            (direction(placed) - Vector((0.0, 0.0, -1.0))).length, 0.0,
            places=5)
        self.assertAlmostEqual(
            (direction(turned) - Vector((-1.0, 0.0, 0.0))).length, 0.0,
            places=5)

    def test_raw_vision_values_are_kept_as_custom_properties(self) -> None:
        obj = self._make(
            radius=400.0,
            multiplier=0.75,
            color=0xFF0080FF,
            spot_angle=60.0,
            fade_start=50.0,
            fade_end=600.0,
            visible_mask=0xFFFFFFFF,
            world_influence_mask=0xFFFFFFFD,
            projected_texture=r"World\Textures\Spot.dds",
            flags=16,
        )

        self.assertEqual(obj["soulworker_class"], "VisLightSource_cl")
        self.assertEqual(obj["soulworker_light_type"], 1)
        self.assertEqual(obj["soulworker_radius"], 400.0)
        self.assertEqual(obj["soulworker_multiplier"], 0.75)
        self.assertEqual(obj["soulworker_color"], -16744193)
        self.assertEqual(obj["soulworker_spot_angle"], 60.0)
        self.assertEqual(obj["soulworker_fade_start"], 50.0)
        self.assertEqual(obj["soulworker_fade_end"], 600.0)
        self.assertEqual(obj["soulworker_visible_mask"], -1)
        self.assertEqual(obj["soulworker_world_influence_mask"], -3)
        self.assertEqual(obj["soulworker_flags"], 16)
        self.assertEqual(
            obj["soulworker_projected_texture"], r"World\Textures\Spot.dds")

    def test_light_nobody_can_see_is_hidden(self) -> None:
        shown = self._make()
        hidden = self._make(visible_mask=0)

        self.assertFalse(shown.hide_viewport or shown.hide_render)
        self.assertTrue(hidden.hide_viewport)
        self.assertTrue(hidden.hide_render)

    def test_object_key_names_the_light(self) -> None:
        self.assertTrue(
            self._make(object_key="CapsuleLight_08").name
            .startswith("CapsuleLight_08"))
        self.assertTrue(self._make().name.startswith("Point"))

    def test_importer_puts_lights_in_a_lights_collection(self) -> None:
        import bpy
        from io_soulworker.core.varchive.objects import LightSource
        from io_soulworker.file_import.scene.importer import (
            SceneImporter,
            SceneImportResult,
        )

        importer = SceneImporter.__new__(SceneImporter)
        first = LightSource()
        first.light_type = LightSource.TYPE_POINT
        second = LightSource()
        second.light_type = LightSource.TYPE_DIRECTIONAL
        unknown = LightSource()
        unknown.light_type = 2

        placed = importer._place_lights([first, unknown, second], self.collection)
        importer._place_lights([first], self.collection)

        lights = self.collection.children["Lights"]
        self.assertEqual(placed, 2)
        self.assertEqual([child.name for child in self.collection.children],
                         ["Lights"])
        self.assertEqual(len(lights.objects), 3)
        self.assertTrue(all(obj.type == "LIGHT" for obj in lights.objects))
        self.assertEqual(len(bpy.data.lights), 3)
        self.assertEqual(SceneImportResult().light_count, 0)
        self.assertEqual(SceneImportResult().objects, [])

    def test_scene_lights_parse_from_a_real_scene(self) -> None:
        from io_soulworker.core.varchive.objects import LightSource
        from io_soulworker.file_import.scene.file_reader import SceneFileReader
        from tests.defines import Defines

        path = (
            Defines.UNPACKED_RESOURCES
            / "World/Scenes/Cloudream/S01_STEELGRAVE/S01_STEELGRAVE.vscene"
        )

        if not path.is_file():
            self.skipTest(f"scene not found: {path}")

        reader = SceneFileReader(path)
        reader.run()
        lights = reader.shapes.lights

        self.assertGreater(len(lights), 0)
        self.assertTrue(all(
            light.light_type in (
                LightSource.TYPE_POINT,
                LightSource.TYPE_DIRECTIONAL,
                LightSource.TYPE_SPOTLIGHT,
            )
            and light.radius >= 0.0
            and light.multiplier >= 0.0
            and light.color >> 24 == 0xFF
            for light in lights
        ))
