import bpy

from logging import debug
from pathlib import Path

from io_soulworker.file_import.animation.chunk_reader import AnimationFileChunkReader


class AnimationFileReader(AnimationFileChunkReader):

    def on_animation(self, skeleton_index: int, name: str) -> None:
        debug(
            f"AnimationFileReader.on_animation: skeleton_index={skeleton_index}, name={name}")

        # bpy.ops.object.mode_set(mode='POSE')

        # bpy.ops.poselib.create_pose_asset(
        #     pose_name=name,
        #     asset_library_reference="LOCAL"
        # )

        # bpy.ops.object.mode_set(mode='OBJECT')

    def __init__(self, path: Path, context: bpy.types.Context) -> None:

        super().__init__(path)

        self.context = context
