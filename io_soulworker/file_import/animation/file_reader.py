import bpy

from collections.abc import Callable
from enum import Enum
from dataclasses import dataclass
from json import loads
from logging import debug
from pathlib import Path

from bpy.types import Action, ArmatureModifier, Bone, Object
from mathutils import Matrix, Quaternion, Vector

from io_soulworker.chunks.atdm_chunk import AtdmChunk
from io_soulworker.chunks.atdo_chunk import AtdoChunk
from io_soulworker.chunks.atdr_chunk import AtdrChunk
from io_soulworker.chunks.bpos_chunk import BposChunk
from io_soulworker.chunks.brot_chunk import BrotChunk
from io_soulworker.chunks.bscl_chunk import BsclChunk
from io_soulworker.chunks.skel_chunk import VisSkeletonChunk_cl
from io_soulworker.file_import.animation.action_builder import (
    group_keyframes_by_bone,
    vision_time_to_frame,
)
from io_soulworker.file_import.animation.chunk_reader import AnimationFileChunkReader
from io_soulworker.unit_scale import vision_to_blender


@dataclass(frozen=True)
class SkeletonBoneRef:
    name: str
    parent_name: str | None
    local_position: Vector
    local_orientation: Quaternion


class AnimationImportSource(Enum):
    """How the importer chooses armature targets."""

    MESH = "mesh"
    """Sidecar import after a model — match scene object name to ``.anim`` stem."""

    USER = "user"
    """Explicit user import — selection when non-empty, otherwise match by name."""


class AnimationFileReader(AnimationFileChunkReader):

    skeletons: list[VisSkeletonChunk_cl]

    def on_animation(self, skeleton_index: int, name: str) -> None:

        assert name, "Animation name cannot be empty"

        debug("Reading animation %s for skeleton index %d", name, skeleton_index)

        self.animation_name = name
        self.skeleton_index = skeleton_index
        self.position_chunk = None
        self.rotation_chunk = None
        self.scale_chunk = None
        self.offset_delta_chunk = None
        self.rotation_delta_chunk = None

    def on_animation_end(self) -> None:

        if self.animation_name is None:
            return

        armature_objects = self._resolve_armature_objects(self.skeleton_index)

        if self.animation_name is not None:
            self._animation_clip_count += 1

        if not armature_objects:
            debug(
                "No armature found for skeleton index %d",
                self.skeleton_index)
            return

        has_bone_tracks = (
            self.position_chunk is not None
            or self.rotation_chunk is not None
            or self.scale_chunk is not None
        )
        has_root_motion = (
            self.offset_delta_chunk is not None
            or self.rotation_delta_chunk is not None
        )

        if not has_bone_tracks and not has_root_motion:
            debug("Animation %s has no supported tracks", self.animation_name)
            return

        for armature_object in armature_objects:
            bone_names = self._bone_names_for_animation(armature_object)
            action_name = self._import_action_name(
                self.animation_name,
                armature_object.name if len(armature_objects) > 1 else None,
            )
            action = self._create_action(action_name)

            animation_data = armature_object.animation_data_create()
            animation_data.action = action

            if has_bone_tracks:
                self._add_transform_curves(
                    action,
                    armature_object,
                    bone_names,
                    self.position_chunk,
                    self.rotation_chunk,
                    self.scale_chunk,
                )

            if has_root_motion:
                self._add_root_motion_curves(
                    action,
                    armature_object,
                    self.offset_delta_chunk,
                    self.rotation_delta_chunk,
                )

        self._applied_animation_count += 1

    def on_skeleton(self, chunk: VisSkeletonChunk_cl) -> None:

        assert len(self.skeletons) < 16

        self.skeletons.append(chunk)

    def on_bone_position(self, chunk: BposChunk) -> None:
        self.position_chunk = chunk

    def on_bone_rotation(self, chunk: BrotChunk) -> None:
        self.rotation_chunk = chunk

    def on_bone_scale(self, chunk: BsclChunk) -> None:
        self.scale_chunk = chunk

    def on_offset_delta(self, chunk: AtdoChunk) -> None:
        self.offset_delta_chunk = chunk

    def on_rotation_delta(self, chunk: AtdrChunk) -> None:
        self.rotation_delta_chunk = chunk

    def on_motion_delta(self, chunk: AtdmChunk) -> None:
        self.offset_delta_chunk = chunk.offset
        self.rotation_delta_chunk = chunk.rotation

    def _report_user_warning(self, key: str, message: str) -> None:

        if self.report_warning is None or key in self._reported_warning_keys:

            return

        self._reported_warning_keys.add(key)
        self.report_warning(message)

    def _has_selection(self) -> bool:

        return bool(self.context.selected_objects)

    def _armatures_by_name(self, skeleton_index: int) -> list[Object]:
        target = self._scene_object_matching_file()

        if target is None:
            return []

        armature = self._armature_from_modifiers(target, skeleton_index)

        if armature is None:
            return []

        return [armature]

    def _scene_object_matching_file(self) -> Object | None:

        stem = self.path.stem
        scene = self.context.scene

        if scene is None:

            return None

        return scene.objects.get(stem)

    def _armature_from_modifiers(
            self,
            obj: Object,
            skeleton_index: int) -> Object | None:
        armatures = [
            modifier.object
            for modifier in obj.modifiers
            if isinstance(modifier, ArmatureModifier)
            and modifier.object is not None
        ]

        if skeleton_index >= len(armatures):
            return None

        chosen = armatures[skeleton_index]

        return chosen

    def _armatures_from_selection(self) -> list[Object]:
        """Armature objects referenced by the current selection."""

        seen: set[int] = set()
        armatures: list[Object] = []

        for obj in self.context.selected_objects:
            if obj.type == 'ARMATURE':
                key = obj.as_pointer()

                if key not in seen:
                    seen.add(key)
                    armatures.append(obj)

            for modifier in obj.modifiers:
                if not isinstance(modifier, ArmatureModifier):
                    continue

                armature = modifier.object

                if armature is None:
                    continue

                key = armature.as_pointer()

                if key not in seen:
                    seen.add(key)
                    armatures.append(armature)

        return armatures

    def _armatures_from_selection_indexed(
            self,
            skeleton_index: int) -> list[Object]:
        armatures = self._armatures_from_selection()

        if not armatures:
            return []

        if skeleton_index == 0:
            return armatures

        if skeleton_index < len(armatures):
            return [armatures[skeleton_index]]

        return []

    def _resolve_armature_objects(self, skeleton_index: int) -> list[Object]:
        """Targets for the animation clip at ``skeleton_index``."""

        if self.import_source == AnimationImportSource.MESH:
            return self._armatures_by_name(skeleton_index)

        if self._has_selection():
            return self._armatures_from_selection_indexed(skeleton_index)

        return self._armatures_by_name(skeleton_index)

    def run(self) -> None:

        super().run()
        self._finish_import()

    def _finish_import(self) -> None:

        if self.import_source != AnimationImportSource.USER:
            return

        if self._applied_animation_count > 0:
            return

        if self._animation_clip_count == 0:
            return

        if self._has_selection():
            message = (
                f'Could not apply "{self.path.name}": '
                "the current selection has no armature to animate."
            )
        else:
            message = (
                f'Could not apply "{self.path.name}": '
                f'no scene object named "{self.path.stem}" with an armature '
                "modifier was found."
            )

        self._report_user_warning("no_targets", message)

    def _skeleton_at_index(
            self,
            skeleton_index: int) -> VisSkeletonChunk_cl | None:
        if skeleton_index >= len(self.skeletons):
            return None

        return self.skeletons[skeleton_index]

    def _bone_names_for_animation(self, armature_object: Object) -> list[str]:
        skeleton = self._skeleton_at_index(self.skeleton_index)

        if skeleton is not None and len(skeleton.bones) >= self.bone_count:
            return [bone.name for bone in skeleton.bones[:self.bone_count]]

        imported_bone_names = armature_object.get(
            "soulworker_bone_names_by_index"
        )

        if imported_bone_names is not None and len(
                imported_bone_names) >= self.bone_count:
            return list(imported_bone_names[:self.bone_count])

        return [bone.name for bone in armature_object.data.bones][:self.bone_count]

    def _import_action_name(
            self,
            animation_name: str,
            armature_name: str | None = None) -> str:
        base = f"{self.path.stem}:{animation_name}"

        if armature_name is None:
            return base

        return f"{base}@{armature_name}"

    def _create_action(self, name: str) -> Action:
        existing = bpy.data.actions.get(name)

        if existing is not None:
            bpy.data.actions.remove(existing)

        return bpy.data.actions.new(name)

    def _add_transform_curves(
        self,
        action: Action,
        armature_object: Object,
        bone_names: list[str],
        position_chunk: BposChunk | None,
        rotation_chunk: BrotChunk | None,
        scale_chunk: BsclChunk | None,
    ) -> None:
        source_refs = self._source_skeleton_refs(bone_names)
        target_refs = self._target_skeleton_refs(armature_object)
        source_names = [bone.name for bone in source_refs[:self.bone_count]]

        position_keys = (
            group_keyframes_by_bone(
                position_chunk.key_frame_list,
                source_names,
                "vector_list",
            )
            if position_chunk is not None
            else {}
        )

        rotation_keys = (
            group_keyframes_by_bone(
                rotation_chunk.key_frame_list,
                source_names,
                "quaternion_list",
            )
            if rotation_chunk is not None
            else {}
        )

        scale_keys = (
            group_keyframes_by_bone(
                scale_chunk.key_frame_list,
                source_names,
                "vector_list",
            )
            if scale_chunk is not None
            else {}
        )

        positions_by_bone = {}
        rotations_by_bone = {}
        scales_by_bone = {}
        source_refs_by_name = {bone.name: bone for bone in source_refs}
        target_refs_by_name = {bone.name: bone for bone in target_refs}
        basis_location_keys_by_bone = {}
        basis_rotation_keys_by_bone = {}
        scale_keys_by_bone = {}
        animated_bone_names: list[str] = []

        for target_ref in target_refs:
            bone_name = target_ref.name
            pose_bone = armature_object.pose.bones.get(bone_name)
            rest_bone = armature_object.data.bones.get(bone_name)

            if pose_bone is None or rest_bone is None:
                continue

            source_ref = source_refs_by_name.get(bone_name)

            if source_ref is None:
                continue

            pose_bone.rotation_mode = 'QUATERNION'
            positions_by_bone[bone_name] = {
                frame: self._remap_translation(
                    vision_to_blender(position.to_3d()),
                    source_ref,
                    target_ref,
                )
                for frame, position in position_keys.get(source_ref.name, [])
            }
            rotations_by_bone[bone_name] = {
                frame: self._remap_rotation(rotation, source_ref, target_ref)
                for frame, rotation in rotation_keys.get(source_ref.name, [])
            }
            scales_by_bone[bone_name] = {
                frame: scale.to_3d()
                for frame, scale in scale_keys.get(source_ref.name, [])
            }
            basis_location_keys_by_bone[bone_name] = []
            basis_rotation_keys_by_bone[bone_name] = []
            scale_keys_by_bone[bone_name] = []
            animated_bone_names.append(bone_name)

        key_frames = sorted({
            frame
            for keys in position_keys.values()
            for frame, _ in keys
        } | {
            frame
            for keys in rotation_keys.values()
            for frame, _ in keys
        } | {
            frame
            for keys in scale_keys.values()
            for frame, _ in keys
        })

        if not key_frames:
            return

        vision_rest_worlds = self._world_matrices_from_refs(target_refs)
        blender_rest_worlds = {
            bone.name: bone.matrix_local.copy()
            for bone in armature_object.data.bones
        }
        frames = range(key_frames[0], key_frames[-1] + 1)

        for frame in frames:
            vision_pose_worlds = self._animated_world_matrices(
                target_refs_by_name,
                positions_by_bone,
                rotations_by_bone,
                frame,
            )

            for bone_name in animated_bone_names:
                rest_bone = armature_object.data.bones.get(bone_name)

                if rest_bone is None:
                    continue

                target_ref = target_refs_by_name[bone_name]
                parent_name = target_ref.parent_name
                basis = self._pose_basis_from_skinning_delta(
                    blender_rest_worlds[bone_name],
                    vision_rest_worlds[bone_name],
                    vision_pose_worlds[bone_name],
                    blender_rest_worlds.get(parent_name) if parent_name else None,
                    vision_rest_worlds.get(parent_name) if parent_name else None,
                    vision_pose_worlds.get(parent_name) if parent_name else None,
                )

                if positions_by_bone.get(bone_name):
                    basis_location_keys_by_bone[bone_name].append(
                        (frame, basis.to_translation())
                    )

                if rotations_by_bone.get(bone_name):
                    basis_rotation_keys_by_bone[bone_name].append(
                        (frame, basis.to_quaternion())
                    )

                if scales_by_bone.get(bone_name):
                    sampled_scale = self._sample_vector_track(
                        scales_by_bone[bone_name],
                        frame,
                    )
                    if sampled_scale is not None:
                        scale_keys_by_bone[bone_name].append(
                            (frame, sampled_scale)
                        )

        for bone_name, keys in basis_location_keys_by_bone.items():
            self._add_vector_curves(
                action,
                armature_object,
                bone_name,
                "location",
                keys,
                3,
            )

        for bone_name, keys in basis_rotation_keys_by_bone.items():
            self._add_vector_curves(
                action,
                armature_object,
                bone_name,
                "rotation_quaternion",
                keys,
                4,
            )

        for bone_name, keys in scale_keys_by_bone.items():
            self._add_vector_curves(
                action,
                armature_object,
                bone_name,
                "scale",
                keys,
                3,
            )

        action.frame_start = int(key_frames[0])
        action.frame_end = int(key_frames[-1])

    def _add_root_motion_curves(
        self,
        action: Action,
        armature_object: Object,
        offset_chunk: AtdoChunk | None,
        rotation_chunk: AtdrChunk | None,
    ) -> None:
        location_keys: list[tuple[int, Vector]] = []
        rotation_keys: list[tuple[int, Quaternion]] = []

        if offset_chunk is not None:
            cumulative = Vector((0.0, 0.0, 0.0))
            for key_frame in offset_chunk.key_frame_list:
                frame = vision_time_to_frame(key_frame.time)
                if offset_chunk.version == 0:
                    cumulative = cumulative + key_frame.offset
                    location_keys.append(
                        (frame, vision_to_blender(cumulative.copy())))
                else:
                    location_keys.append(
                        (frame, vision_to_blender(key_frame.offset.copy())))

        if rotation_chunk is not None:
            cumulative_angle = 0.0
            for key_frame in rotation_chunk.key_frame_list:
                frame = vision_time_to_frame(key_frame.time)
                if rotation_chunk.version == 0:
                    cumulative_angle += key_frame.angle
                    angle = cumulative_angle
                else:
                    angle = key_frame.angle

                if rotation_chunk.axis == AtdrChunk.AXIS_X:
                    rotation = Quaternion(Vector((1.0, 0.0, 0.0)), angle)
                elif rotation_chunk.axis == AtdrChunk.AXIS_Z:
                    rotation = Quaternion(Vector((0.0, 0.0, 1.0)), angle)
                else:
                    rotation = Quaternion(Vector((0.0, 1.0, 0.0)), angle)

                rotation_keys.append((frame, rotation))

        if location_keys:
            self._add_object_vector_curves(
                action,
                armature_object,
                "location",
                location_keys,
                3,
            )

        if rotation_keys:
            armature_object.rotation_mode = 'QUATERNION'
            self._add_object_vector_curves(
                action,
                armature_object,
                "rotation_quaternion",
                [
                    (frame, Vector((rotation.w, rotation.x, rotation.y, rotation.z)))
                    for frame, rotation in rotation_keys
                ],
                4,
            )

        if location_keys or rotation_keys:
            root_frames = [frame for frame, _ in location_keys] + [
                frame for frame, _ in rotation_keys
            ]
            start = min(root_frames)
            end = max(root_frames)
            action.frame_start = min(
                int(action.frame_start), start) if action.frame_end else start
            action.frame_end = max(int(action.frame_end), end)

    def _add_object_vector_curves(
        self,
        action: Action,
        obj: Object,
        property_name: str,
        keys: list[tuple[int, Vector]],
        component_count: int,
    ) -> None:
        if not keys:
            return

        for component in range(component_count):
            fcurve = self._ensure_fcurve(
                action,
                obj,
                property_name,
                component,
                obj.name,
            )

            for frame, value in keys:
                keyframe = fcurve.keyframe_points.insert(
                    frame,
                    float(value[component]),
                    options={'FAST'},
                )
                keyframe.interpolation = 'LINEAR'

            fcurve.update()

    def _source_skeleton_refs(
            self,
            fallback_bone_names: list[str]) -> list[SkeletonBoneRef]:
        skeleton = self._skeleton_at_index(self.skeleton_index)

        if skeleton is not None:
            return self._bone_refs_from_chunk(skeleton)

        return [
            SkeletonBoneRef(
                name=bone_name,
                parent_name=None,
                local_position=Vector((0.0, 0.0, 0.0)),
                local_orientation=Quaternion(),
            )
            for bone_name in fallback_bone_names
        ]

    @staticmethod
    def _bone_refs_from_chunk(
            chunk: VisSkeletonChunk_cl) -> list[SkeletonBoneRef]:
        bone_names_by_id = {bone.id: bone.name for bone in chunk.bones}

        return [
            SkeletonBoneRef(
                name=bone.name,
                parent_name=bone_names_by_id.get(bone.parent_id),
                local_position=vision_to_blender(bone.local_space_position),
                local_orientation=bone.local_space_orientation,
            )
            for bone in chunk.bones
        ]

    def _target_skeleton_refs(
            self,
            armature_object: Object) -> list[SkeletonBoneRef]:
        serialized = armature_object.get("soulworker_skeleton")

        if serialized:
            try:
                return self._bone_refs_from_metadata(loads(serialized))
            except Exception:
                debug("Failed to read SoulWorker skeleton metadata from armature")

        return self._bone_refs_from_armature(armature_object)

    @staticmethod
    def _bone_refs_from_metadata(bones: list[dict]) -> list[SkeletonBoneRef]:
        names_by_id = {
            index: bone["name"]
            for index, bone in enumerate(bones)
        }

        return [
            SkeletonBoneRef(
                name=bone["name"],
                parent_name=names_by_id.get(bone["parent_id"]),
                local_position=Vector(bone["local_position"]),
                local_orientation=Quaternion(bone["local_orientation"]),
            )
            for bone in bones
        ]

    def _bone_refs_from_armature(
            self, armature_object: Object) -> list[SkeletonBoneRef]:
        refs = []

        for bone in armature_object.data.bones:
            rest_local = self._rest_local_matrix(bone)
            refs.append(
                SkeletonBoneRef(
                    name=bone.name,
                    parent_name=bone.parent.name if bone.parent is not None else None,
                    local_position=rest_local.to_translation(),
                    local_orientation=rest_local.to_quaternion(),
                ))

        return refs

    @staticmethod
    def _remap_translation(
            position: Vector,
            source_ref: SkeletonBoneRef,
            target_ref: SkeletonBoneRef) -> Vector:
        source_position = position.to_3d()
        source_length = source_ref.local_position.length

        if source_length <= 0.000001:
            return target_ref.local_position + \
                (source_position - source_ref.local_position)

        target_length = target_ref.local_position.length
        scale = target_length / source_length

        return (
            (source_position - source_ref.local_position) * scale
            + target_ref.local_position
        )

    @staticmethod
    def _remap_rotation(
            rotation: Quaternion,
            source_ref: SkeletonBoneRef,
            target_ref: SkeletonBoneRef) -> Quaternion:
        correction = target_ref.local_orientation @ source_ref.local_orientation.inverted()
        remapped = correction @ rotation
        remapped.normalize()

        return remapped

    @staticmethod
    def _rest_local_matrix(rest_bone: Bone) -> Matrix:
        if rest_bone.parent is None:
            return rest_bone.matrix_local.copy()

        return rest_bone.parent.matrix_local.inverted() @ rest_bone.matrix_local

    @staticmethod
    def _compose_local_matrix(
            position: Vector,
            orientation: Quaternion) -> Matrix:
        matrix = orientation.to_matrix().to_4x4()
        matrix.translation = position.to_3d()

        return matrix

    @classmethod
    def _world_matrices_from_refs(
            cls,
            refs: list[SkeletonBoneRef]) -> dict[str, Matrix]:
        refs_by_name = {ref.name: ref for ref in refs}
        worlds: dict[str, Matrix] = {}

        def build(name: str) -> Matrix:
            cached = worlds.get(name)

            if cached is not None:
                return cached

            ref = refs_by_name[name]
            local = cls._compose_local_matrix(
                ref.local_position,
                ref.local_orientation,
            )

            if ref.parent_name and ref.parent_name in refs_by_name:
                matrix = build(ref.parent_name) @ local
            else:
                matrix = local

            worlds[name] = matrix

            return matrix

        for ref in refs:
            build(ref.name)

        return worlds

    def _animated_world_matrices(
        self,
        refs_by_name: dict[str, SkeletonBoneRef],
        positions_by_bone: dict[str, dict[int, Vector]],
        rotations_by_bone: dict[str, dict[int, Quaternion]],
        frame: int,
    ) -> dict[str, Matrix]:
        worlds: dict[str, Matrix] = {}

        def build(name: str) -> Matrix:
            cached = worlds.get(name)

            if cached is not None:
                return cached

            ref = refs_by_name[name]
            position = self._sample_vector_track(
                positions_by_bone.get(name, {}),
                frame,
            )
            rotation = self._sample_quaternion_track(
                rotations_by_bone.get(name, {}),
                frame,
            )

            if position is None:
                position = ref.local_position

            if rotation is None:
                rotation = ref.local_orientation

            local = self._compose_local_matrix(position, rotation)

            if ref.parent_name and ref.parent_name in refs_by_name:
                matrix = build(ref.parent_name) @ local
            else:
                matrix = local

            worlds[name] = matrix

            return matrix

        for name in refs_by_name:
            build(name)

        return worlds

    @staticmethod
    def _pose_basis_from_skinning_delta(
        blender_rest: Matrix,
        vision_rest: Matrix,
        vision_pose: Matrix,
        parent_blender_rest: Matrix | None,
        parent_vision_rest: Matrix | None,
        parent_vision_pose: Matrix | None,
    ) -> Matrix:
        """Map a Vision joint delta onto a Blender rest pose with a different tail."""

        delta = vision_pose @ vision_rest.inverted()

        if (
            parent_blender_rest is None
            or parent_vision_rest is None
            or parent_vision_pose is None
        ):
            return blender_rest.inverted() @ delta @ blender_rest

        parent_delta = parent_vision_pose @ parent_vision_rest.inverted()

        return (
            blender_rest.inverted()
            @ parent_delta.inverted()
            @ delta
            @ blender_rest
        )

    @staticmethod
    def _local_animation_matrix(
            rest_local: Matrix,
            position: Vector | None,
            rotation: Quaternion | None) -> Matrix:
        desired = rest_local.copy()

        if rotation is not None:
            desired = rotation.to_matrix().to_4x4()
            desired.translation = rest_local.to_translation()

        if position is not None:
            desired.translation = position.to_3d()

        return desired

    @staticmethod
    def _sample_vector_track(
            keys_by_frame: dict[int, Vector], frame: int) -> Vector | None:
        if not keys_by_frame:
            return None

        if frame in keys_by_frame:
            return keys_by_frame[frame]

        frames = sorted(keys_by_frame)
        floor = None
        ceiling = None

        for key_frame in frames:
            if key_frame < frame:
                floor = key_frame
                continue

            ceiling = key_frame
            break

        if floor is None:
            return keys_by_frame[ceiling]

        if ceiling is None:
            return keys_by_frame[floor]

        factor = (frame - floor) / (ceiling - floor)

        return keys_by_frame[floor].lerp(keys_by_frame[ceiling], factor)

    @staticmethod
    def _sample_quaternion_track(
        keys_by_frame: dict[int, Quaternion],
        frame: int,
    ) -> Quaternion | None:
        if not keys_by_frame:
            return None

        if frame in keys_by_frame:
            return keys_by_frame[frame]

        frames = sorted(keys_by_frame)
        floor = None
        ceiling = None

        for key_frame in frames:
            if key_frame < frame:
                floor = key_frame
                continue

            ceiling = key_frame
            break

        if floor is None:
            return keys_by_frame[ceiling]

        if ceiling is None:
            return keys_by_frame[floor]

        factor = (frame - floor) / (ceiling - floor)
        sampled = keys_by_frame[floor].slerp(keys_by_frame[ceiling], factor)
        sampled.normalize()

        return sampled

    def _add_vector_curves(
        self,
        action: Action,
        armature_object: Object,
        bone_name: str,
        property_name: str,
        keys: list[tuple[int, Vector]],
        component_count: int = 3,
    ) -> None:
        if not keys:
            return

        data_path = f'pose.bones["{
            self._escape_bone_name(bone_name)}"].{property_name}'

        for component in range(component_count):
            fcurve = self._ensure_fcurve(
                action,
                armature_object,
                data_path,
                component,
                bone_name,
            )

            for frame, value in keys:
                keyframe = fcurve.keyframe_points.insert(
                    frame,
                    float(value[component]),
                    options={'FAST'},
                )
                keyframe.interpolation = 'LINEAR'

            fcurve.update()

    @staticmethod
    def _ensure_fcurve(
        action: Action,
        armature_object: Object,
        data_path: str,
        component: int,
        group_name: str,
    ):
        if hasattr(action, "fcurve_ensure_for_datablock"):
            return action.fcurve_ensure_for_datablock(
                armature_object,
                data_path,
                index=component,
                group_name=group_name,
            )

        return action.fcurves.new(data_path=data_path, index=component)

    @staticmethod
    def _escape_bone_name(name: str) -> str:
        return name.replace("\\", "\\\\").replace('"', '\\"')

    def __init__(
        self,
        path: Path,
        context: bpy.types.Context,
        *,
        import_source: AnimationImportSource = AnimationImportSource.USER,
        report_error: Callable[[str], None] | None = None,
        report_warning: Callable[[str], None] | None = None,
    ) -> None:

        super().__init__(path)

        self.context = context
        self.import_source = import_source
        self.report_error = report_error
        self.report_warning = report_warning
        self._reported_warning_keys: set[str] = set()
        self._animation_clip_count = 0
        self._applied_animation_count = 0
        self.skeletons = []
        self.animation_name = None
        self.skeleton_index = 0
        self.position_chunk = None
        self.rotation_chunk = None
        self.scale_chunk = None
        self.offset_delta_chunk = None
        self.rotation_delta_chunk = None
