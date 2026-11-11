from __future__ import annotations

from os import getenv
from pathlib import Path
from unittest import SkipTest, TestCase

from tests.defines import Defines


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_SCENE_RELATIVE = Path(
    "World/Scenes/Cloudream/S01_STEELGRAVE/S01_STEELGRAVE.vscene"
)


class TestSceneEntityModels(TestCase):

    def test_scene_entities_capture_model_paths(self) -> None:
        """Parse SHPS without placing meshes — assert entity model paths."""

        try:
            from io_soulworker.file_import.scene.file_reader import (
                SceneFileReader,
            )
        except ImportError as exc:
            raise SkipTest(_BLENDER_HINT) from exc

        root = Defines.UNPACKED_RESOURCES
        scene_path = root / _SCENE_RELATIVE

        if not scene_path.is_file():
            self.skipTest(f"scene not found: {scene_path}")

        reader = SceneFileReader(scene_path)
        reader.run()

        self.assertIsNotNone(reader.shapes)
        assert reader.shapes is not None

        with_models = [
            entity
            for entity in reader.shapes.entities
            if entity.model_path
        ]

        self.assertGreater(
            len(with_models),
            0,
            "expected entities with VModelSerializationProxy paths",
        )

        model_paths = {entity.model_path.lower() for entity in with_models}
        self.assertTrue(
            any(path.endswith(".model") for path in model_paths),
            model_paths,
        )

    def test_shader_textures_resolve_with_explicit_root(self) -> None:

        try:
            from io_soulworker.file_import.runner import in_blender
            from io_soulworker.file_import.shaders.node_groups import (
                _load_resource_image,
            )
            import bpy
        except ImportError as exc:
            raise SkipTest(_BLENDER_HINT) from exc

        if not in_blender():
            raise SkipTest(_BLENDER_HINT)

        from tempfile import TemporaryDirectory

        bpy.ops.wm.read_factory_settings(use_empty=True)

        with TemporaryDirectory() as folder:
            root = Path(folder) / "unpacked"
            texture = root / "Textures" / "ToonTexture.png"
            texture.parent.mkdir(parents=True)
            image = bpy.data.images.new("Toon", width=1, height=1)
            image.filepath_raw = str(texture)
            image.file_format = 'PNG'
            image.save()

            # No N-panel property in a factory session: only the explicit
            # root can locate the texture, with case-insensitive matching.
            self.assertFalse(hasattr(bpy.context.scene,
                                     "soulworker_unpack_resources"))
            self.assertIsNone(_load_resource_image(
                r"textures\toontexture.png"))
            loaded = _load_resource_image(r"textures\toontexture.png", root)
            self.assertIsNotNone(loaded)
            self.assertEqual(Path(bpy.path.abspath(loaded.filepath)).resolve(),
                             texture.resolve())

    def test_preferred_action_falls_back_to_single_clip_sequence(self) -> None:

        try:
            from io_soulworker.file_import.runner import in_blender
            from io_soulworker.file_import.scene.importer import SceneImporter
            import bpy
        except ImportError as exc:
            raise SkipTest(_BLENDER_HINT) from exc

        if not in_blender():
            raise SkipTest(_BLENDER_HINT)

        bpy.ops.wm.read_factory_settings(use_empty=True)
        mesh = bpy.data.meshes.new("Cat")
        obj = bpy.data.objects.new("Cat", mesh)
        rig = bpy.data.objects.new("CatRig", bpy.data.armatures.new("CatRig"))
        bpy.context.collection.objects.link(obj)
        bpy.context.collection.objects.link(rig)
        obj.modifiers.new("Armature", "ARMATURE").object = rig
        only = bpy.data.actions.new("cat01:zzz")
        bpy.data.actions.new("other:idle")

        importer = SceneImporter.__new__(SceneImporter)
        importer._apply_preferred_action(obj, "cat01", "idle")

        self.assertIsNotNone(rig.animation_data)
        self.assertEqual(rig.animation_data.action, only)

        bpy.data.actions.new("cat01:run")
        rig.animation_data.action = None
        importer._apply_preferred_action(obj, "cat01", "idle")
        self.assertIsNone(rig.animation_data.action)

    def test_scene_import_places_model_entities(self) -> None:

        if getenv("SOULWORKER_BLENDER_IMPORT") != "1":
            self.skipTest("set SOULWORKER_BLENDER_IMPORT=1 to run")

        try:
            from io_soulworker.file_import.runner import in_blender
            from io_soulworker.file_import.scene.importer import SceneImporter
            import bpy
        except ImportError as exc:
            raise SkipTest(_BLENDER_HINT) from exc

        if not in_blender():
            raise SkipTest(_BLENDER_HINT)

        root = Defines.UNPACKED_RESOURCES
        scene_path = root / _SCENE_RELATIVE

        if not scene_path.is_file():
            self.skipTest(f"scene not found: {scene_path}")

        bpy.ops.wm.read_factory_settings(use_empty=True)

        result = SceneImporter(
            scene_path,
            bpy.context,
            root,
        ).run()

        self.assertGreater(result.entity_count, 0)

        model_objects = [
            obj
            for obj in result.objects
            if str(obj.get("soulworker_path", "")).lower().endswith(".model")
        ]

        self.assertGreater(len(model_objects), 0)

        animated = [
            obj
            for obj in model_objects
            if any(
                modifier.type == "ARMATURE" and modifier.object is not None
                and modifier.object.animation_data is not None
                and modifier.object.animation_data.action is not None
                for modifier in obj.modifiers
            )
        ]

        # Not every entity has a sibling .anim; only require that import
        # completed and at least one model object exists. Prefer an action
        # when preferred_animation is set on any placed object.
        preferred = [
            obj
            for obj in model_objects
            if obj.get("soulworker_preferred_animation")
        ]

        if preferred:
            self.assertGreater(
                len(animated),
                0,
                "entities with preferred_animation should bind an action",
            )
