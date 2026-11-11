"""Export a Blender mesh + armature as a SoulWorker dynamic .model file.

Chunk sequence expected by the Vision VDynamicMesh loader:

    VBIN header
    VMSH  - vertex/index buffer (pos/normal/uv, skinned)
    MTRS  - material list (nested MTRL envelopes)
    SUBM  - sub-mesh ranges (one per material)
    EXPR  - export transform (identity 3x4)
    SKEL  - skeleton bones (name, parent, local + inverse matrices)
    WGHT  - per-vertex bone weights (uint16 bone index + quantized weight)
    BBBX  - per-bone bounding boxes
    CBPR  - custom bone property strings
    BNDS  - mesh bounding box + sphere + collision box
    EOF   - sentinel (int32 -1)
"""

from __future__ import annotations

from json import loads
from pathlib import Path

from mathutils import Matrix, Quaternion, Vector

from ..chunks.bbbx_chunk import BBBXChunk
from ..chunks.bnds_chunk import BNDSChunk
from ..chunks.cbpr_chunk import CBPRChunk
from ..chunks.expr_chunk import ExprChunk
from ..chunks.mtrs_chunk import MtrsChunk
from ..chunks.skel_chunk import (
    VisSkeletalBone_cl,
    VisSkeletonChunk_cl,
)
from ..chunks.subm_chunk import VisSubMeshChunk
from ..chunks.vmsh_chunk import VMshChunk
from ..chunks.wght_chunk import WGHTChunk
from ..core.binary_writer import BinaryWriter
from ..core.vis_bin_header import VisBinHeader
from ..core.vis_bounding_box import HavokBoundingBox
from ..core.vis_chunk_id import VisChunkId
from ..core.vis_chunk_writer_scope import (
    VisChunkWriterScope,
    write_chunk_file_eof,
)
from ..file_export.materials_xml import MaterialSidecar
from ..file_export.mesh_builder import (
    GeometryBuild,
    build_geometry,
    build_material_sidecars,
    mtrs_from_sidecars,
)
from ..file_export.resources_xml import (
    rebase_material_resources,
    write_export_sidecars,
)
from ..file_import.model.skeleton_builder import build_bone_transforms
from ..unit_scale import blender_matrix_to_vision, blender_to_vision


_MAX_WEIGHTS_PER_VERTEX = 4


class ModelExportData:
    """Serializable payload for a dynamic .model file."""

    def __init__(
        self,
        mesh: VMshChunk,
        materials: list[MtrsChunk],
        sidecars: list[MaterialSidecar],
        sub_meshes: VisSubMeshChunk,
        export_transform: ExprChunk,
        skeleton: VisSkeletonChunk_cl,
        weights: list[WGHTChunk],
        bounding_boxes: BBBXChunk,
        cbpr: CBPRChunk,
        bnds: BNDSChunk,
    ) -> None:

        self.mesh = mesh
        self.materials = materials
        self.sidecars = sidecars
        self.sub_meshes = sub_meshes
        self.export_transform = export_transform
        self.skeleton = skeleton
        self.weights = weights
        self.bounding_boxes = bounding_boxes
        self.cbpr = cbpr
        self.bnds = bnds


def _ordered_bones(armature_obj) -> list:

    armature = armature_obj.data
    stored = armature_obj.get("soulworker_bone_names_by_index")

    if not stored:

        return list(armature.bones)

    by_name = {bone.name: bone for bone in armature.bones}
    ordered = []
    seen: set[str] = set()

    for name in stored:

        bone = by_name.get(name)

        if bone is None or name in seen:

            continue

        ordered.append(bone)
        seen.add(name)

    for bone in armature.bones:

        if bone.name not in seen:

            ordered.append(bone)

    return ordered


def _bone_index_map(armature_obj) -> dict[str, int]:

    return {
        bone.name: index
        for index, bone in enumerate(_ordered_bones(armature_obj))
    }


def _parent_bone_id(bone, name_to_index: dict[str, int]) -> int:

    if bone.parent is None:

        return VisSkeletalBone_cl.PARENT_BONE_INVALID_ID

    return name_to_index.get(
        bone.parent.name,
        VisSkeletalBone_cl.PARENT_BONE_INVALID_ID,
    )


def _skeleton_from_import(armature_obj) -> VisSkeletonChunk_cl | None:
    """Replay the SKEL chunk captured at import.

    The model viewer draws the blue hierarchy from local space and the green
    bone positions from inverse object space. Rebuilding those from Blender's
    Y-along-bone rest pose does not match Vision's stored quaternions.
    """

    raw = armature_obj.get("soulworker_skeleton")

    if not raw:

        return None

    try:

        payload = loads(raw)

    except (TypeError, ValueError):

        return None

    if not payload:

        return None

    if [entry["name"] for entry in payload] != [
            bone.name for bone in _ordered_bones(armature_obj)]:
        return None

    skeleton = VisSkeletonChunk_cl()
    skeleton.version = VisSkeletonChunk_cl.VERSION
    skeleton.bone_mask_count = 0

    for index, entry in enumerate(payload):

        bone = VisSkeletalBone_cl()
        bone.id = index
        bone.name = entry["name"]
        bone.parent_id = int(entry["parent_id"])
        if "inverse_position" in entry and "inverse_orientation" in entry:
            bone.inverse_object_space_position = Vector(
                entry["inverse_position"])
            bone.inverse_object_space_orientation = Quaternion(
                entry["inverse_orientation"])
        bone.local_space_position = blender_to_vision(
            Vector(entry["local_position"]))
        bone.local_space_orientation = Quaternion(entry["local_orientation"])
        skeleton.bones.append(bone)

    def local_matrix(bone):
        matrix = bone.local_space_orientation.to_matrix().to_4x4()
        matrix.translation = bone.local_space_position
        return matrix

    # Older imports stored native local transforms but no inverse bind data.
    # Reconstruct from those, never from the old pretty-bone display axes.
    transforms = build_bone_transforms(skeleton.bones, local_matrix)
    for entry, bone, transform in zip(payload, skeleton.bones, transforms):
        if "inverse_position" not in entry or "inverse_orientation" not in entry:
            inverse = transform.matrix.inverted()
            bone.inverse_object_space_position = inverse.translation
            bone.inverse_object_space_orientation = inverse.to_quaternion()

    return skeleton


def _build_skeleton(armature_obj) -> VisSkeletonChunk_cl:

    imported = _skeleton_from_import(armature_obj)

    if imported is not None:

        return imported

    bones = _ordered_bones(armature_obj)
    name_to_index = {bone.name: index for index, bone in enumerate(bones)}
    skeleton = VisSkeletonChunk_cl()
    skeleton.version = VisSkeletonChunk_cl.VERSION
    skeleton.bone_mask_count = 0

    world_matrices: dict[str, Matrix] = {}

    for bone in bones:

        world = bone.matrix_local.copy()
        world_matrices[bone.name] = blender_matrix_to_vision(world)

    for bone in bones:

        sw_bone = VisSkeletalBone_cl()
        sw_bone.id = name_to_index[bone.name]
        sw_bone.name = bone.name
        sw_bone.parent_id = _parent_bone_id(bone, name_to_index)

        world_matrix = world_matrices[bone.name]

        try:

            inverse = world_matrix.inverted()

        except ValueError:

            inverse = Matrix.Identity(4)

        sw_bone.inverse_object_space_position = Vector(inverse.translation)
        sw_bone.inverse_object_space_orientation = inverse.to_quaternion()

        if bone.parent is not None:

            parent_world = world_matrices[bone.parent.name]
            local_matrix = parent_world.inverted() @ world_matrix

        else:

            local_matrix = world_matrix

        sw_bone.local_space_position = Vector(local_matrix.translation)
        sw_bone.local_space_orientation = local_matrix.to_quaternion()

        skeleton.bones.append(sw_bone)

    return skeleton


def _build_weights(
        mesh_obj,
        name_to_index: dict[str, int],
        source_vertex_indices: list[int]) -> list[WGHTChunk]:

    mesh = mesh_obj.data
    vertex_groups = mesh_obj.vertex_groups
    result: list[WGHTChunk] = []

    for source_vert_index in source_vertex_indices:

        vertex = mesh.vertices[source_vert_index]
        chunk = WGHTChunk()
        entries: list[tuple[int, float]] = []

        for group_element in vertex.groups:

            group = vertex_groups[group_element.group]

            if group is None:

                continue

            bone_index = name_to_index.get(group.name)

            if bone_index is None or group_element.weight <= 0.0:

                continue

            entries.append((bone_index, group_element.weight))

        entries.sort(key=lambda item: item[1], reverse=True)
        entries = entries[:_MAX_WEIGHTS_PER_VERTEX]
        total = sum(weight for _, weight in entries)
        scale = (1.0 / total) if total > 0.0 else 0.0

        for bone_index, weight in entries:

            entity = WGHTChunk.Entity()
            entity.bone_index = bone_index
            entity.weight = weight * scale
            chunk.values.append(entity)

        result.append(chunk)

    return result


def _stored_bone_bounds(armature_obj) -> dict[str, tuple[Vector, Vector]]:
    """Per-bone boxes captured at import, keyed by bone name."""

    raw = armature_obj.get("soulworker_bone_bounds")

    if not raw:

        return {}

    try:

        payload = loads(raw)

    except (TypeError, ValueError):

        return {}

    result = {}

    for entry in payload:

        try:

            result[entry["name"]] = (
                Vector(entry["min"]), Vector(entry["max"]))

        except (KeyError, TypeError, ValueError):

            continue

    return result


def _build_bounding_boxes(armature_obj) -> BBBXChunk:
    """BBBX: one bone-space box per bone, in skeleton order.

    Replay the boxes captured at import. Bones without a stored box get an
    empty box, which is what many shipped models (PC_B among them) carry; the
    engine then falls back to the mesh bounds. Writing the whole mesh box for
    every bone draws a cage of oversized boxes in the model viewer.
    """

    bbbx = BBBXChunk()

    if armature_obj is None:

        return bbbx

    stored = _stored_bone_bounds(armature_obj)

    for bone in _ordered_bones(armature_obj):

        entity = BBBXChunk.Entity()
        entity.bounds = HavokBoundingBox()
        box = stored.get(bone.name)

        if box is None:

            entity.bounds.min = Vector((0.0, 0.0, 0.0))
            entity.bounds.max = Vector((0.0, 0.0, 0.0))

        else:

            entity.bounds.min = box[0].copy()
            entity.bounds.max = box[1].copy()

        bbbx.values.append(entity)

    return bbbx


def _build_cbpr(armature_obj) -> CBPRChunk:

    cbpr = CBPRChunk()

    if armature_obj is not None:

        cbpr.values = ["" for _ in _ordered_bones(armature_obj)]

    return cbpr


def _build_bnds(mesh_bounds: HavokBoundingBox) -> BNDSChunk:

    bnds = BNDSChunk()
    bnds.bounding_box = mesh_bounds

    center = (mesh_bounds.min + mesh_bounds.max) * 0.5
    radius = (mesh_bounds.max - mesh_bounds.min).length * 0.5
    bnds.bounding_sphere_radius = Vector(
        (center.x, center.y, center.z, radius))

    bnds.collision_bounding_box = HavokBoundingBox()
    bnds.collision_bounding_box.min = mesh_bounds.min.copy()
    bnds.collision_bounding_box.max = mesh_bounds.max.copy()

    return bnds


def _build_export_transform() -> ExprChunk:

    expr = ExprChunk()
    expr.version = ExprChunk.LOCAL_VERSION
    expr.matrix = Matrix.Identity(4)
    expr.flag = 0

    return expr


def build_model_from_blender_object(
        mesh_obj,
        armature_obj=None,
        resources_root: Path | None = None) -> ModelExportData:

    transform = (
        armature_obj.matrix_world.inverted() @ mesh_obj.matrix_world
        if armature_obj is not None else None
    )
    geometry: GeometryBuild = build_geometry(mesh_obj, transform=transform)
    sidecars = build_material_sidecars(mesh_obj, resources_root)
    materials = mtrs_from_sidecars(sidecars)
    export_transform = _build_export_transform()

    skeleton = VisSkeletonChunk_cl()
    weights: list[WGHTChunk] = []

    if armature_obj is not None:

        skeleton = _build_skeleton(armature_obj)
        weights = _build_weights(
            mesh_obj,
            _bone_index_map(armature_obj),
            geometry.source_vertex_indices,
        )

    bounding_boxes = _build_bounding_boxes(armature_obj)
    cbpr = _build_cbpr(armature_obj)
    bnds = _build_bnds(geometry.mesh.bounding_box)

    return ModelExportData(
        mesh=geometry.mesh,
        materials=materials,
        sidecars=sidecars,
        sub_meshes=geometry.sub_meshes,
        export_transform=export_transform,
        skeleton=skeleton,
        weights=weights,
        bounding_boxes=bounding_boxes,
        cbpr=cbpr,
        bnds=bnds,
    )


def _write_mtrs_chunk(writer: BinaryWriter, materials: list[MtrsChunk]) -> None:

    with VisChunkWriterScope(writer, VisChunkId.MTRS) as payload:

        payload.write_uint32(len(materials))

        for material in materials:

            material.write(payload)


def write_model_file(
        path: Path | str,
        mesh_obj,
        armature_obj=None,
        resources_root: Path | None = None) -> None:

    target = Path(path)
    data = build_model_from_blender_object(
        mesh_obj, armature_obj, resources_root)
    data.sidecars = rebase_material_resources(
        target, data.sidecars, resources_root)
    data.materials = mtrs_from_sidecars(data.sidecars)
    target.parent.mkdir(parents=True, exist_ok=True)

    with BinaryWriter(target.open("wb")) as writer:

        header = VisBinHeader()
        header.cid = VisChunkId.VBIN
        header.version = 65536
        header.write(writer)

        with VisChunkWriterScope(writer, VisChunkId.VMSH) as payload:

            data.mesh.write(payload)

        _write_mtrs_chunk(writer, data.materials)

        with VisChunkWriterScope(writer, VisChunkId.SUBM) as payload:

            data.sub_meshes.write(payload)

        with VisChunkWriterScope(writer, VisChunkId.EXPR) as payload:

            data.export_transform.write(payload)

        if data.skeleton.bones:

            with VisChunkWriterScope(writer, VisChunkId.SKEL) as payload:

                data.skeleton.write(payload)

            with VisChunkWriterScope(writer, VisChunkId.WGHT) as payload:

                payload.write_uint32(1)

                for wght in data.weights:

                    wght.write(payload)

            with VisChunkWriterScope(writer, VisChunkId.BBBX) as payload:

                data.bounding_boxes.write(payload)

            with VisChunkWriterScope(writer, VisChunkId.CBPR) as payload:

                data.cbpr.write(payload)

        with VisChunkWriterScope(writer, VisChunkId.BNDS) as payload:

            data.bnds.write(payload)

        write_chunk_file_eof(writer)

    write_export_sidecars(
        target,
        data.sidecars,
        resources_root=resources_root,
    )
