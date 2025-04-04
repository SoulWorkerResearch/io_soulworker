from itertools import islice
from typing import cast
import bpy

from logging import debug
from pathlib import Path

from io_soulworker.file_import.animation.chunk_reader import AnimationFileChunkReader


class AnimationFileReader(AnimationFileChunkReader):

    def on_animation(self, skeleton_index: int, name: str) -> None:

        assert name, "Animation name cannot be empty"

        debug(f"Creating animation {name} for skeleton index {skeleton_index}")

        view_layer = self.context.view_layer
        if view_layer is None:
            debug("No view layer found")
            return

        active = view_layer.objects.active
        if active is None:
            debug("No active object found")
            return

        f = filter(
            lambda obj: obj.type == 'ARMATURE',
            active.modifiers
        )

        armature = next(islice(f, skeleton_index, skeleton_index + 1), None)

        if armature is None:
            debug(f"No armature found for skeleton index {skeleton_index}")
            return

        assert isinstance(armature, bpy.types.ArmatureModifier), "Bad type"

        assert armature.object, "Armature object is None"

        view_layer.objects.active = armature.object
        bpy.ops.object.mode_set(mode='POSE')

        assert isinstance(armature.object.data, bpy.types.Armature), "Bad type"

        for bone in armature.object.data.bones:
            bone.select = True

        bpy.ops.poselib.create_pose_asset(
            pose_name=name,
            asset_library_reference="LOCAL"
        )

        bpy.ops.object.mode_set(mode='OBJECT')
        view_layer.objects.active = active

    def __init__(self, path: Path, context: bpy.types.Context) -> None:

        super().__init__(path)

        self.context = context
