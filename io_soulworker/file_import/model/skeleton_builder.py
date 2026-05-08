from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar


TBone = TypeVar("TBone")
TMatrix = TypeVar("TMatrix")


@dataclass(frozen=True)
class BoneTransform:
    id: int
    name: str
    parent_id: int
    parent_name: str | None
    matrix: TMatrix


def build_bone_transforms(
    bones: Iterable[TBone],
    local_matrix_of: Callable[[TBone], TMatrix],
) -> list[BoneTransform]:
    bone_list = list(bones)
    bones_by_id = {bone.id: bone for bone in bone_list}
    transforms_by_id: dict[int, BoneTransform] = {}

    def build(bone: TBone) -> BoneTransform:
        cached = transforms_by_id.get(bone.id)
        if cached is not None:
            return cached

        local_matrix = local_matrix_of(bone)
        parent_name = None
        matrix = local_matrix

        if bone.parent_id != -1:
            parent = bones_by_id[bone.parent_id]
            parent_transform = build(parent)
            parent_name = parent.name
            matrix = parent_transform.matrix @ local_matrix

        transform = BoneTransform(
            id=bone.id,
            name=bone.name,
            parent_id=bone.parent_id,
            parent_name=parent_name,
            matrix=matrix,
        )
        transforms_by_id[bone.id] = transform

        return transform

    return [build(bone) for bone in bone_list]
