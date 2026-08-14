from dataclasses import dataclass
from json import dumps

import bpy
from mathutils import Matrix, Vector

from io_soulworker.chunks.skel_chunk import VisSkeletalBone_cl
from io_soulworker.chunks.skel_chunk import VisSkeletonChunk_cl
from io_soulworker.file_import.model.skeleton_builder import build_bone_transforms
from io_soulworker.unit_scale import vision_to_blender


class NameHelper:

    @staticmethod
    def of_armature_object(name: str) -> str:

        return name + "_Armature"

    @staticmethod
    def of_armature_modifier(name: str) -> str:

        return name + "_Modifier"


class BoneHelper:

    DEFAULT_LENGTH = 0.1

    @staticmethod
    def apply_rest_transform(edit_bone, matrix):

        rotation = matrix.to_quaternion()
        head = matrix.to_translation()
        tail_offset = rotation @ Vector((0.0, BoneHelper.DEFAULT_LENGTH, 0.0))
        roll_axis = rotation @ Vector((0.0, 0.0, 1.0))

        edit_bone.head = head
        edit_bone.tail = head + tail_offset
        edit_bone.align_roll(roll_axis)

    @staticmethod
    def ensure_tail(edit_bone):

        if (edit_bone.tail - edit_bone.head).length > 0.000001:

            return

        vec = Vector((0.0, BoneHelper.DEFAULT_LENGTH, 0.0))

        edit_bone.tail = edit_bone.head + vec


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
) -> ArmatureBuildResult:
    active_object = context.view_layer.objects.active

    if active_object is not None and getattr(active_object, "mode", "OBJECT") != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    armature = bpy.data.armatures.new(
        NameHelper.of_armature_object(name)
    )

    armature.display_type = 'STICK'

    armature_object = bpy.data.objects.new(
        NameHelper.of_armature_object(name),
        armature
    )

    context.collection.objects.link(armature_object)
    context.view_layer.objects.active = armature_object
    armature_object.select_set(True)

    bpy.ops.object.mode_set(mode="EDIT")

    def bone_local_matrix(bone: VisSkeletalBone_cl) -> Matrix:
        matrix = bone.local_space_orientation.to_matrix().to_4x4()
        matrix.translation = vision_to_blender(bone.local_space_position)

        return matrix

    bone_transforms = build_bone_transforms(chunk.bones, bone_local_matrix)
    edit_bones_by_id = {}

    for bone, transform in zip(chunk.bones, bone_transforms):
        new = armature.edit_bones.new(bone.name)

        BoneHelper.apply_rest_transform(new, transform.matrix)
        edit_bones_by_id[bone.id] = new

    for transform in bone_transforms:

        if transform.parent_id != VisSkeletalBone_cl.PARENT_BONE_INVALID_ID:

            child_bone = edit_bones_by_id[transform.id]
            parent_bone = edit_bones_by_id[transform.parent_id]
            child_bone.parent = parent_bone
            child_bone.use_connect = False

    bpy.ops.object.mode_set(mode="OBJECT")

    context.view_layer.objects.active = armature_object
    context.view_layer.update()

    bone_names_by_index = [bone.name for bone in chunk.bones]
    armature_object["soulworker_bone_names_by_index"] = bone_names_by_index
    armature_object["soulworker_skeleton"] = dumps([
        {
            "name": bone.name,
            "parent_id": bone.parent_id,
            "local_position": _vector_to_list(bone.local_space_position),
            "local_orientation": _quaternion_to_list(bone.local_space_orientation),
        }
        for bone in chunk.bones
    ])

    return ArmatureBuildResult(
        armature=armature,
        object=armature_object,
        bone_names_by_index=bone_names_by_index,
    )
