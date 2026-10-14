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
    r"World\Scenes\Cloudream\S01_STEELGRAVE\S01_STEELGRAVE.vscene"
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
