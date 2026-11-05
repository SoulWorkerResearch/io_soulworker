from dataclasses import dataclass
from json import dumps

import bpy
from mathutils import Matrix, Vector

from io_soulworker.chunks.skel_chunk import VisSkeletalBone_cl
from io_soulworker.chunks.skel_chunk import VisSkeletonChunk_cl
from io_soulworker.file_import.model.skeleton_builder import (
    BoneTransform,
    build_bone_transforms,
)
from io_soulworker.unit_scale import vision_to_blender


class NameHelper:

    @staticmethod
    def of_armature_object(name: str) -> str:

        return name + "_Armature"

    @staticmethod
    def of_armature_modifier(name: str) -> str:

        return name + "_Modifier"


CONNECT_EPSILON = 1e-5
PRIMARY_CHILD_PENALTY = 0.5
PRETTY_BONE_SHAPE_NAME = "SoulWorker_BoneDisplay"


def _pretty_bone_shape() -> bpy.types.Object:
    """One unlinked wire shape shared by all imported pose bones."""
    existing = bpy.data.objects.get(PRETTY_BONE_SHAPE_NAME)
    if existing is not None and existing.get("soulworker_bone_display"):
        return existing

    mesh = bpy.data.meshes.new(PRETTY_BONE_SHAPE_NAME)
    mesh.from_pydata(
        [(0, 0, 0), (0, 1, 0),
         (0.04, 0.2, 0), (-0.04, 0.2, 0),
         (0, 0.2, 0.04), (0, 0.2, -0.04)],
        [(0, side) for side in range(2, 6)]
        + [(side, 1) for side in range(2, 6)]
        + [(2, 4), (4, 3), (3, 5), (5, 2)],
        [],
    )
    mesh.update()
    shape = bpy.data.objects.new(PRETTY_BONE_SHAPE_NAME, mesh)
    shape["soulworker_bone_display"] = True
    return shape


def _is_deprioritized_child_name(name: str) -> bool:

    return "Twist" in name or name.startswith("Fx_")


def _children_by_parent_id(
        bones: list[VisSkeletalBone_cl]) -> dict[int, list[VisSkeletalBone_cl]]:
    children: dict[int, list[VisSkeletalBone_cl]] = {}

    for bone in bones:

        if bone.parent_id == VisSkeletalBone_cl.PARENT_BONE_INVALID_ID:

            continue

        children.setdefault(bone.parent_id, []).append(bone)

    return children


def _world_translation(
        transforms_by_id: dict[int, BoneTransform],
        bone_id: int) -> Vector:

    return transforms_by_id[bone_id].matrix.to_translation()


def _primary_child(
        bone: VisSkeletalBone_cl,
        children: list[VisSkeletalBone_cl],
        transforms_by_id: dict[int, BoneTransform],
) -> VisSkeletalBone_cl | None:

    if not children:

        return None

    head = _world_translation(transforms_by_id, bone.id)
    best: VisSkeletalBone_cl | None = None
    best_score = -float("inf")

    for child in children:
        distance = (_world_translation(
            transforms_by_id, child.id) - head).length
        if distance <= CONNECT_EPSILON:
            continue
        score = distance

        if _is_deprioritized_child_name(child.name):

            score -= PRIMARY_CHILD_PENALTY

        if score > best_score:

            best_score = score
            best = child

    return best


def _segment_lengths_by_parent(
        children_by_parent_id: dict[int, list[VisSkeletalBone_cl]],
        transforms_by_id: dict[int, BoneTransform],
) -> dict[int, list[float]]:
    lengths: dict[int, list[float]] = {}

    for parent_id, children in children_by_parent_id.items():

        parent_head = _world_translation(transforms_by_id, parent_id)

        for child in children:
            distance = (
                _world_translation(transforms_by_id, child.id) - parent_head
            ).length

            if distance > CONNECT_EPSILON:

                lengths.setdefault(parent_id, []).append(distance)

    return lengths


def _average_segment_length(
        parent_id: int,
        segment_lengths_by_parent: dict[int, list[float]],
        *,
        default: float,
) -> float:

    lengths = segment_lengths_by_parent.get(parent_id)

    if not lengths:

        return default

    return sum(lengths) / len(lengths)


def _leaf_tail(
        head: Vector,
        bone: VisSkeletalBone_cl,
        world_matrix: Matrix,
        transforms_by_id: dict[int, BoneTransform],
        segment_lengths_by_parent: dict[int, list[float]],
        *,
        default_length: float,
) -> Vector:

    if bone.parent_id != VisSkeletalBone_cl.PARENT_BONE_INVALID_ID:

        parent_head = _world_translation(transforms_by_id, bone.parent_id)
        direction = head - parent_head

        if direction.length > CONNECT_EPSILON:

            return head + direction.normalized() * direction.length

    direction = world_matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))

    if direction.length <= CONNECT_EPSILON:

        direction = Vector((0.0, default_length, 0.0))

    else:

        direction = direction.normalized() * _average_segment_length(
            bone.parent_id,
            segment_lengths_by_parent,
            default=default_length,
        )

    return head + direction


class BoneHelper:

    DEFAULT_LENGTH = 0.1

    @staticmethod
    def apply_rest_transform(
            edit_bone: bpy.types.EditBone,
            bone: VisSkeletalBone_cl,
            world_matrix: Matrix,
            children_by_parent_id: dict[int, list[VisSkeletalBone_cl]],
            transforms_by_id: dict[int, BoneTransform],
            segment_lengths_by_parent: dict[int, list[float]]) -> Matrix:

        head = world_matrix.to_translation()
        edit_bone.head = head

        primary = _primary_child(
            bone,
            children_by_parent_id.get(bone.id, []),
            transforms_by_id,
        )

        if primary is not None:

            edit_bone.tail = _world_translation(transforms_by_id, primary.id)

        else:

            edit_bone.tail = _leaf_tail(
                head,
                bone,
                world_matrix,
                transforms_by_id,
                segment_lengths_by_parent,
                default_length=BoneHelper.DEFAULT_LENGTH,
            )

        if (edit_bone.tail - edit_bone.head).length <= CONNECT_EPSILON:

            BoneHelper.ensure_tail(edit_bone)

        roll_axis = world_matrix.to_3x3() @ Vector((0.0, 0.0, 1.0))
        edit_bone.align_roll(roll_axis)
        display_matrix = edit_bone.matrix.copy()

        # Keep native axes for skinning; rotate only the pose display shape.
        edit_bone.matrix = world_matrix
        return world_matrix.inverted() @ display_matrix

    @staticmethod
    def ensure_tail(edit_bone: bpy.types.EditBone) -> None:

        if (edit_bone.tail - edit_bone.head).length > CONNECT_EPSILON:

            return

        edit_bone.tail = edit_bone.head + Vector(
            (0.0, BoneHelper.DEFAULT_LENGTH, 0.0),
        )


@dataclass(frozen=True)
class ArmatureBuildResult:
    armature: bpy.types.Armature
    object: bpy.types.Object
    bone_names_by_index: list[str]


def _vector_to_list(vector) -> list[float]:
    return [float(vector[index]) for index in range(3)]


def _quaternion_to_list(quaternion) -> list[float]:
    return [
        float(quaternion.w),
        float(quaternion.x),
        float(quaternion.y),
        float(quaternion.z),
    ]


def build_armature_from_skeleton(
    context: bpy.types.Context,
    name: str,
    chunk: VisSkeletonChunk_cl,
    *,
    collection: bpy.types.Collection | None = None,
) -> ArmatureBuildResult:
    active_object = context.view_layer.objects.active

    if active_object is not None and getattr(
            active_object, "mode", "OBJECT") != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    armature = bpy.data.armatures.new(
        NameHelper.of_armature_object(name)
    )

    armature.display_type = 'STICK'

    armature_object = bpy.data.objects.new(
        NameHelper.of_armature_object(name),
        armature
    )

    target = collection or context.collection
    target.objects.link(armature_object)
    context.view_layer.objects.active = armature_object
    armature_object.select_set(True)

    bpy.ops.object.mode_set(mode="EDIT")

    def bone_local_matrix(bone: VisSkeletalBone_cl) -> Matrix:
        matrix = bone.local_space_orientation.to_matrix().to_4x4()
        matrix.translation = vision_to_blender(bone.local_space_position)

        return matrix

    bone_transforms = build_bone_transforms(chunk.bones, bone_local_matrix)
    transforms_by_id = {
        transform.id: transform for transform in bone_transforms}
    children_by_parent_id = _children_by_parent_id(chunk.bones)
    segment_lengths_by_parent = _segment_lengths_by_parent(
        children_by_parent_id,
        transforms_by_id,
    )
    edit_bones_by_id: dict[int, bpy.types.EditBone] = {}
    display_rotations_by_name = {}

    for bone, transform in zip(chunk.bones, bone_transforms):
        new = armature.edit_bones.new(bone.name)

        display_matrix = BoneHelper.apply_rest_transform(
            new,
            bone,
            transform.matrix,
            children_by_parent_id,
            transforms_by_id,
            segment_lengths_by_parent,
        )
        display_rotations_by_name[new.name] = display_matrix.to_euler()
        edit_bones_by_id[bone.id] = new

    for transform in bone_transforms:

        if transform.parent_id != VisSkeletalBone_cl.PARENT_BONE_INVALID_ID:

            child_bone = edit_bones_by_id[transform.id]
            parent_bone = edit_bones_by_id[transform.parent_id]
            child_bone.parent = parent_bone
            child_bone.use_connect = False

    # Vision animates local translations even when a joint coincides with its
    # parent's tail. Blender connected bones ignore those location channels and
    # can also snap twist joints to a tail chosen only for display.

    bpy.ops.object.mode_set(mode="OBJECT")

    # Vision composes object-space translation/rotation without parent scale;
    # each bone's scale is applied only when building its skinning matrix.
    for bone in armature.bones:
        bone.inherit_scale = 'NONE'

    shape = _pretty_bone_shape()
    for pose_bone in armature_object.pose.bones:
        pose_bone.custom_shape = shape
        pose_bone.use_custom_shape_bone_size = True
        pose_bone.custom_shape_rotation_euler = display_rotations_by_name[
            pose_bone.name]

    context.view_layer.objects.active = armature_object
    context.view_layer.update()

    bone_names_by_index = [bone.name for bone in chunk.bones]
    armature_object["soulworker_bone_names_by_index"] = bone_names_by_index
    armature_object["soulworker_skeleton"] = dumps([
        {
            "name": bone.name,
            "parent_id": bone.parent_id,
            "local_position": _vector_to_list(
                vision_to_blender(bone.local_space_position)),
            "local_orientation": _quaternion_to_list(
                bone.local_space_orientation),
            "inverse_position": _vector_to_list(
                bone.inverse_object_space_position),
            "inverse_orientation": _quaternion_to_list(
                bone.inverse_object_space_orientation),
        }
        for bone in chunk.bones
    ])

    return ArmatureBuildResult(
        armature=armature,
        object=armature_object,
        bone_names_by_index=bone_names_by_index,
    )
