from __future__ import annotations

from os import getenv
from pathlib import Path
from types import SimpleNamespace
from unittest import SkipTest, TestCase


class TestSkeletalAnimation(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from io_soulworker.file_import.runner import in_blender
        except ImportError as exc:
            raise SkipTest("requires Blender") from exc

        if not in_blender():
            raise SkipTest("requires Blender")

    def tearDown(self) -> None:
        import bpy
        from io_soulworker.file_import.model.file_reader import clear_mesh_cache

        clear_mesh_cache()
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def assertMatrixClose(self, actual, expected, tolerance=2e-5):
        self.assertLess(
            max(abs(actual[i][j] - expected[i][j])
                for i in range(4) for j in range(4)),
            tolerance,
        )

    def _skeleton(self):
        from mathutils import Matrix, Quaternion, Vector
        from io_soulworker.chunks.skel_chunk import (
            VisSkeletalBone_cl, VisSkeletonChunk_cl,
        )

        chunk = VisSkeletonChunk_cl()
        world = Matrix.Identity(4)
        for index, (name, position) in enumerate([
            ("Root", (0.0, 0.0, 0.0)),
            ("ArmTwist", (20.0, 0.0, 0.0)),
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
            chunk.bones.append(bone)
        return chunk

    def test_native_axes_and_twist_positions_survive_armature_build(self):
        import bpy
        from mathutils import Matrix
        from io_soulworker.file_import.armature_builder import (
            build_armature_from_skeleton,
        )
        from io_soulworker.unit_scale import vision_to_blender

        chunk = self._skeleton()
        result = build_armature_from_skeleton(bpy.context, "Test", chunk)
        world = Matrix.Identity(4)
        for source in chunk.bones:
            world = world @ Matrix.Translation(
                vision_to_blender(source.local_space_position))
            target = result.armature.bones[source.name]
            self.assertFalse(target.use_connect)
            self.assertMatrixClose(target.matrix_local, world)

    def test_pretty_shapes_follow_joint_chain_without_changing_native_axes(self):
        import bpy
        from mathutils import Vector
        from io_soulworker.file_import.armature_builder import build_armature_from_skeleton

        first = build_armature_from_skeleton(
            bpy.context, "Pretty", self._skeleton())
        second = build_armature_from_skeleton(
            bpy.context, "PrettyAgain", self._skeleton())
        shape = first.object.pose.bones["Root"].custom_shape
        self.assertIsNotNone(shape)
        self.assertEqual(len(shape.users_collection), 0)
        for result in (first, second):
            for name, expected in (("Root", (0.2, 0, 0)),
                                   ("ArmTwist", (0.4, 0, 0))):
                pose = result.object.pose.bones[name]
                self.assertEqual(pose.custom_shape, shape)
                displayed_tip = pose.bone.matrix_local @ (
                    pose.custom_shape_rotation_euler.to_matrix()
                    @ Vector((0, pose.bone.length, 0)))
                self.assertLess(
                    (displayed_tip - Vector(expected)).length, 1e-5)
                self.assertFalse(pose.bone.use_connect)

    def test_scaled_parent_and_translated_child_match_skinning(self):
        import bpy
        from mathutils import Matrix, Quaternion, Vector
        from io_soulworker.file_import.armature_builder import (
            build_armature_from_skeleton,
        )
        from io_soulworker.file_import.animation.file_reader import (
            AnimationFileReader,
        )

        chunk = self._skeleton()
        result = build_armature_from_skeleton(bpy.context, "Test", chunk)
        reader = AnimationFileReader(Path("test.anim"), bpy.context)
        reader.skeletons = [chunk]
        reader.bone_count = 2
        arm = result.object
        action = bpy.data.actions.new("Scaled translation")
        arm.animation_data_create().action = action
        positions = [Vector((0, 0, 0)), Vector((35, 10, 0))]
        rotations = [Quaternion((0, 0, 1), 0.5), Quaternion((0, 1, 0), 0.4)]
        scales = [Vector((2, 0.5, 1)), Vector((1, 1, 1))]
        reader._add_transform_curves(
            action, arm, result.bone_names_by_index,
            SimpleNamespace(key_frame_list=[
                SimpleNamespace(time=0.0, vector_list=positions)]),
            SimpleNamespace(key_frame_list=[
                SimpleNamespace(time=0.0, quaternion_list=rotations)]),
            SimpleNamespace(key_frame_list=[
                SimpleNamespace(time=0.0, vector_list=scales)]),
        )
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        expected = Matrix.Identity(4)
        for index, bone in enumerate(chunk.bones):
            expected = expected @ Matrix.LocRotScale(
                positions[index] / 100, rotations[index], None)
            # Vision applies local scale to this joint's skinning transform,
            # without propagating it into descendants' positions or rotations.
            self.assertMatrixClose(
                arm.pose.bones[bone.name].matrix,
                expected @ Matrix.Diagonal((*scales[index], 1.0)))

    def test_root_motion_moves_mesh_and_keeps_scene_placement(self):
        import bpy
        from mathutils import Matrix, Vector
        from io_soulworker.file_import.model.file_reader import ModelFileReader

        placement = Matrix.Translation((3.0, 4.0, 5.0))
        reader = ModelFileReader(
            Path("test.model"), bpy.context, 7.0,
            matrix_world=placement, reuse_mesh=False,
        )
        reader.mesh.from_pydata([(0.2, 0.1, 0.0)], [], [])
        reader._link_object()
        reader.on_skeleton(self._skeleton())
        reader.bone_index_to_vertex_group[1].add([0], 1.0, 'REPLACE')
        reader._apply_transform()
        bpy.context.view_layer.update()
        mesh = reader.object
        arm = mesh.modifiers[0].object
        self.assertMatrixClose(mesh.matrix_world, placement)
        self.assertMatrixClose(arm.matrix_world, placement)
        self.assertMatrixClose(mesh.matrix_local, Matrix.Identity(4))

        arm.location += Vector((0.0, 0.5, 0.0))
        bpy.context.view_layer.update()
        evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        self.assertLess((
            evaluated.matrix_world @ evaluated.data.vertices[0].co
            - Vector((3.2, 4.6, 5.0))
        ).length, 1e-5)

    def test_root_motion_accumulates_version_one_deltas(self):
        import bpy
        from mathutils import Vector
        from io_soulworker.file_import.armature_builder import build_armature_from_skeleton
        from io_soulworker.file_import.animation.file_reader import AnimationFileReader

        arm = build_armature_from_skeleton(
            bpy.context, "RootMotion", self._skeleton()).object
        action = bpy.data.actions.new("Root deltas")
        arm.animation_data_create().action = action
        reader = AnimationFileReader(Path("test.anim"), bpy.context)
        offsets = SimpleNamespace(version=1, key_frame_list=[
            SimpleNamespace(time=index / 33, offset=Vector((0.0, value, 0.0)))
            for index, value in enumerate((90.0, 20.0, 30.0))
        ])
        rotations = SimpleNamespace(version=1, axis=0, key_frame_list=[
            SimpleNamespace(time=index / 33, angle=value)
            for index, value in enumerate((0.0, 45.0, 45.0))
        ])
        reader._add_root_motion_curves(action, arm, offsets, rotations)
        for frame, expected in ((1, 0.0), (2, 0.2), (3, 0.5)):
            bpy.context.scene.frame_set(frame)
            self.assertAlmostEqual(arm.location.y, expected, places=6)
        self.assertLess((
            arm.rotation_quaternion @ Vector((1.0, 0.0, 0.0))
            - Vector((0.0, 1.0, 0.0))
        ).length, 1e-5)

    def test_offset_track_versions_roundtrip_as_deltas(self):
        from struct import pack
        from tempfile import TemporaryDirectory
        from io_soulworker.chunks.atdo_chunk import AtdoChunk
        from io_soulworker.core.binary_reader import BinaryReader
        from io_soulworker.core.binary_writer import BinaryWriter

        with TemporaryDirectory() as folder:
            path = Path(folder) / "offset.bin"
            for version, values in ((0, (0, 20, 50)), (1, (0, 20, 30))):
                encoded = pack('<HI', version, len(values)) + b''.join(
                    pack('<ffff', index / 30, 0, value, 0)
                    for index, value in enumerate(values))
                path.write_bytes(encoded)
                with BinaryReader(path) as reader:
                    chunk = AtdoChunk.from_reader(reader)
                self.assertEqual(
                    [key.offset.y for key in chunk.key_frame_list], [0, 20, 30])
                with path.open('wb') as stream, BinaryWriter(stream) as writer:
                    chunk.write(writer)
                self.assertEqual(path.read_bytes(), encoded)

    def test_pc_b_attack_meshes_match_file_skinning(self):
        """Compare evaluated Blender vertices with independent LBS from SKEL/WGHT."""
        import bpy
        from mathutils import Matrix, Vector
        from io_soulworker.file_import.model.chunk_reader import ModelChunkReader
        from io_soulworker.file_import.model.file_reader import ModelFileReader
        from io_soulworker.file_import.animation.chunk_reader import (
            AnimationFileChunkReader,
        )
        from io_soulworker.file_import.animation.file_reader import (
            AnimationFileReader,
        )
        from io_soulworker.unit_scale import vision_to_blender

        root = Path(getenv(
            "SOULWORKER_RESOURCES",
            "A:/SteamLibrary/steamapps/common/Soulworker_KR/_datas",
        )) / "Character/Player/PC_B"
        model_path = root / "PC_B.model"
        clips = [root / f"PC_B_B_N_Attack_{number}_P.anim"
                 for number in ("06", "04")]
        if not all(path.is_file() for path in [model_path, *clips]):
            self.skipTest(
                "PC_B resources unavailable; set SOULWORKER_RESOURCES")

        class RawModel(ModelChunkReader):
            def on_mesh(self, chunk):
                self.mesh = chunk

            def on_skeleton(self, chunk):
                self.skeleton = chunk

            def on_skeleton_weights(self, reader):
                self.weights = reader.all_of(len(self.mesh.vertices))

        class RawAnimation(AnimationFileChunkReader):
            def on_skeleton(self, chunk):
                self.skeleton = chunk

            def on_bone_position(self, chunk):
                self.positions = chunk.key_frame_list

            def on_bone_rotation(self, chunk):
                self.rotations = chunk.key_frame_list

            def on_bone_scale(self, chunk):
                self.scales = chunk.key_frame_list

            def on_offset_delta(self, chunk):
                self.offsets = chunk.key_frame_list

        raw = RawModel(model_path)
        raw.run()
        obj = ModelFileReader(
            model_path, bpy.context, 7.0, reuse_mesh=False).run()
        arm = obj.modifiers[0].object
        inverses = []
        for bone in raw.skeleton.bones:
            inverse = bone.inverse_object_space_orientation.to_matrix().to_4x4()
            inverse.translation = vision_to_blender(
                bone.inverse_object_space_position)
            inverses.append(inverse)

        for weights in raw.weights:
            self.assertTrue(all(
                value.bone_index < len(inverses) for value in weights.values))
            self.assertAlmostEqual(
                sum(value.weight for value in weights.values), 1.0, delta=5e-5)

        def sample(keys, time, index, attribute, quaternion=False):
            # Compare skinning at the importer's quantized key times. Timing
            # resampling is separate from the bone/weight conversion under test.
            for left, right in zip(keys, keys[1:]):
                start = round(left.time * 33) / 33
                end = round(right.time * 33) / 33
                if start <= time <= end:
                    factor = (time - start) / (end - start)
                    a = getattr(left, attribute)[index]
                    b = getattr(right, attribute)[index]
                    return a.slerp(b, factor) if quaternion else a.lerp(b, factor)
            key = keys[0] if time < keys[0].time else keys[-1]
            return getattr(key, attribute)[index]

        for path in clips:
            source = RawAnimation(path)
            source.run()
            # These clips share the model's rest skeleton and bone order.
            self.assertEqual(
                [b.name for b in source.skeleton.bones],
                [b.name for b in raw.skeleton.bones],
            )
            for a, b in zip(source.skeleton.bones, raw.skeleton.bones):
                self.assertLess(
                    (a.local_space_position - b.local_space_position).length, 1e-5)
                self.assertLess(
                    a.local_space_orientation.rotation_difference(
                        b.local_space_orientation).angle, 1e-5)
            AnimationFileReader(path, bpy.context, target_object=obj).run()
            accumulated = Vector((0.0, 0.0, 0.0))
            root_keys = []
            for index, key in enumerate(source.offsets):
                if index > 0:
                    accumulated += key.offset
                root_keys.append(SimpleNamespace(
                    time=key.time, vector_list=[accumulated.copy()]))
            end = round(source.positions[-1].time * 33) + 1
            max_vertex_error = 0.0
            worst = None
            max_matrix_error = 0.0
            for frame in range(1, end + 1):
                time = (frame - 1) / 33
                root_position = vision_to_blender(
                    sample(root_keys, time, 0, "vector_list"))
                root_motion = Matrix.Translation(root_position)
                worlds = []
                skinning = []
                for index, bone in enumerate(source.skeleton.bones):
                    position = sample(source.positions, time,
                                      index, "vector_list")
                    rotation = sample(source.rotations, time, index,
                                      "quaternion_list", quaternion=True)
                    scale = sample(source.scales, time, index, "vector_list")
                    world = Matrix.LocRotScale(
                        vision_to_blender(position.to_3d()), rotation, None)
                    if bone.parent_id >= 0:
                        world = worlds[bone.parent_id] @ world
                    worlds.append(world)
                    skinning.append(world @ Matrix.Diagonal(
                        (*scale.to_3d(), 1.0)) @ inverses[index])
                bpy.context.scene.frame_set(frame)
                for index, bone in enumerate(source.skeleton.bones):
                    actual = arm.pose.bones[bone.name].matrix @ arm.data.bones[bone.name].matrix_local.inverted()
                    max_matrix_error = max(max_matrix_error, max(
                        abs(actual[i][j] - skinning[index][i][j])
                        for i in range(4) for j in range(4)))
                evaluated = obj.evaluated_get(
                    bpy.context.evaluated_depsgraph_get())
                mesh = evaluated.to_mesh()
                try:
                    for index, weights in enumerate(raw.weights):
                        position = vision_to_blender(raw.mesh.vertices[index])
                        expected = Vector((0, 0, 0))
                        total = sum(value.weight for value in weights.values)
                        for value in weights.values:
                            expected += (skinning[value.bone_index] @ position
                                         * (value.weight / total))
                        # Root motion belongs to the whole character. Compare in
                        # world space, without reproducing modifier-space errors.
                        expected = root_motion @ expected
                        vertex_error = (
                            evaluated.matrix_world @ mesh.vertices[index].co - expected).length
                        if vertex_error > max_vertex_error:
                            max_vertex_error = vertex_error
                            worst = (frame, index, tuple(
                                mesh.vertices[index].co), tuple(expected))
                finally:
                    evaluated.to_mesh_clear()
            print(f"{path.name}: {end} frames, {len(raw.weights)} vertices, "
                  f"max skinning error {max_vertex_error:.8f} m")
            self.assertLess(max_matrix_error, 2e-4, path.name)
            self.assertLess(max_vertex_error, 2e-4, (path.name, worst))
