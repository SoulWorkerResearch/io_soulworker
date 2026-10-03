from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mathutils import Vector

from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.subm_chunk import VisMeshBuffer_cl, VisSubMeshChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.vis_bounding_box import HavokBoundingBox
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_index_format import VisIndexFormat
from io_soulworker.core.vis_mesh_effect_config import VisEffectConfig_cl
from io_soulworker.core.vis_prim_type import VisPrimitiveType
from io_soulworker.core.vis_render_state import VisRenderState
from io_soulworker.core.vis_render_state_flags import VisRenderStateFlag
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.core.vis_vertex_descriptor import VisMBVertexDescriptor_cl
from io_soulworker.file_export.materials_xml import (
    DEFAULT_DIFFUSE,
    MaterialSidecar,
)
from io_soulworker.file_import.model.surface_nodes import spec_exp_from_roughness
from io_soulworker.file_import.resource_path import game_relative_texture_path
from io_soulworker.file_import.shaders.node_groups import (
    collect_shader_from_material,
)
from io_soulworker.unit_scale import blender_to_vision


_POS_OFFSET = 0x3000
_NORMAL_OFFSET = 0x300C
_TEX0_OFFSET = 0x2018

_DEFAULT_RENDER_FLAGS = (
    VisRenderStateFlag.FRONTFACE
    | VisRenderStateFlag.FILTERING
    | VisRenderStateFlag.USEADDITIVEALPHA
)


@dataclass
class GeometryBuild:
    mesh: VMshChunk
    sub_meshes: VisSubMeshChunk
    source_vertex_indices: list[int]


def bounding_box_from_points(points: list[Vector]) -> HavokBoundingBox:

    box = HavokBoundingBox()

    if not points:

        box.min = Vector((0.0, 0.0, 0.0))
        box.max = Vector((0.0, 0.0, 0.0))
        return box

    mn = Vector(points[0])
    mx = Vector(points[0])

    for point in points[1:]:

        mn.x = min(mn.x, point.x)
        mn.y = min(mn.y, point.y)
        mn.z = min(mn.z, point.z)
        mx.x = max(mx.x, point.x)
        mx.y = max(mx.y, point.y)
        mx.z = max(mx.z, point.z)

    box.min = mn
    box.max = mx
    return box


def make_vertex_descriptor() -> VisMBVertexDescriptor_cl:

    descriptor = VisMBVertexDescriptor_cl()
    descriptor.header_size = 48
    descriptor.stride = 32
    descriptor.pos_offset = _POS_OFFSET
    descriptor.normal_offset = _NORMAL_OFFSET
    descriptor.tex_offset = [
        VisMBVertexDescriptor_cl.UNSET_OFFSET
    ] * VisMBVertexDescriptor_cl.MAX_TEXTURES
    descriptor.tex_offset[0] = _TEX0_OFFSET
    descriptor.first_text_coord = 255

    return descriptor


def _vertex_and_normal_transforms(obj):

    vertex_transform = obj.matrix_world.to_3x3()

    try:

        normal_transform = vertex_transform.inverted().transposed()

    except ValueError:

        normal_transform = vertex_transform.copy()

    return vertex_transform, normal_transform


def _image_path_from_node(node, resources_root: Path | None) -> str:

    image = getattr(node, "image", None)

    if image is None or not getattr(image, "filepath", ""):

        return ""

    return game_relative_texture_path(image.filepath, resources_root)


def _named_image_path(
        material,
        name: str,
        resources_root: Path | None) -> str:

    if material is None or not material.use_nodes or material.node_tree is None:

        return ""

    node = material.node_tree.nodes.get(name)

    if node is None:

        return ""

    return _image_path_from_node(node, resources_root)


def _principled_node(material):

    if material is None or not material.use_nodes or material.node_tree is None:

        return None

    node = material.node_tree.nodes.get("Principled BSDF")

    if node is not None:

        return node

    for candidate in material.node_tree.nodes:

        if candidate.bl_idname == "ShaderNodeBsdfPrincipled":

            return candidate

    return None


def _linked_image_path(
        material,
        socket_name: str,
        resources_root: Path | None) -> str:

    principled = _principled_node(material)

    if principled is None:

        return ""

    socket = principled.inputs.get(socket_name)

    if socket is None:

        return ""

    for link in socket.links:

        path = _image_path_from_node(link.from_node, resources_root)

        if path:

            return path

    return ""


def _diffuse_from_blender_material(
        material,
        resources_root: Path | None) -> str:

    named = _named_image_path(material, "Diffuse", resources_root)

    if named:

        return named

    linked = _linked_image_path(material, "Base Color", resources_root)

    if linked:

        return linked

    return DEFAULT_DIFFUSE


def _specular_from_blender_material(
        material,
        resources_root: Path | None) -> tuple[float, float, str]:

    spec_mul = 0.0
    spec_exp = 2.0
    principled = _principled_node(material)

    if principled is not None:

        spec_socket = principled.inputs.get("Specular IOR Level")

        if spec_socket is not None:

            spec_mul = float(spec_socket.default_value)

        rough_socket = principled.inputs.get("Roughness")

        if rough_socket is not None:

            spec_exp = spec_exp_from_roughness(
                float(rough_socket.default_value))

    specular_map = _named_image_path(material, "Specular", resources_root)

    return spec_mul, spec_exp, specular_map


def _transparency_from_blender_material(
        material) -> tuple[VisTransparencyType, float]:

    if material is None:

        return VisTransparencyType.NONE, -1.0

    blend = getattr(material, "blend_method", "OPAQUE")
    threshold = float(getattr(material, "alpha_threshold", -1.0))

    if blend == "CLIP":

        return VisTransparencyType.ALPHATEST, threshold

    if blend in {"BLEND", "HASHED"}:

        return VisTransparencyType.ALPHA, threshold

    return VisTransparencyType.NONE, -1.0


def material_sidecar_from_blender(
        material,
        resources_root: Path | None = None) -> MaterialSidecar:

    if material is None:

        return MaterialSidecar(name="default")

    spec_mul, spec_exp, specular_map = _specular_from_blender_material(
        material,
        resources_root,
    )
    transparency, alphathreshold = _transparency_from_blender_material(
        material)
    doublesided = not bool(getattr(material, "use_backface_culling", True))
    shader = collect_shader_from_material(material, resources_root)

    sidecar = MaterialSidecar(
        name=material.name or "material",
        diffuse=_diffuse_from_blender_material(material, resources_root),
        specular=specular_map,
        normal=_named_image_path(material, "Normal", resources_root),
        transparency=transparency,
        doublesided=doublesided,
        spec_mul=spec_mul,
        spec_exp=spec_exp,
        alphathreshold=alphathreshold,
    )

    if shader is not None:

        sidecar.shader_library_stem, sidecar.shader_effect, sidecar.paramstring = (
            shader
        )

    return sidecar


def build_material_sidecars(
        mesh_obj,
        resources_root: Path | None = None) -> list[MaterialSidecar]:

    slots = list(mesh_obj.data.materials)

    if not slots:

        return [MaterialSidecar(name="default")]

    return [
        material_sidecar_from_blender(slot, resources_root)
        for slot in slots
    ]


def mtrs_from_sidecars(sidecars: list[MaterialSidecar]) -> list[MtrsChunk]:

    return [sidecar.to_mtrs_chunk() for sidecar in sidecars]


def _faces_are_all_sharp(mesh) -> bool:

    attr = mesh.attributes.get("sharp_face")

    if attr is not None:

        return bool(attr.data) and all(item.value for item in attr.data)

    polygons = mesh.polygons

    if not polygons or not hasattr(polygons[0], "use_smooth"):

        return False

    return not any(polygon.use_smooth for polygon in polygons)


def _loop_export_normal(
        mesh,
        loop_index: int,
        vertex_index: int,
        use_vertex_normals: bool) -> Vector:
    """Prefer authored split normals; fall back to vertex normals on flat meshes."""

    if use_vertex_normals:

        return Vector(mesh.vertices[vertex_index].normal)

    if loop_index < len(mesh.corner_normals):

        return Vector(mesh.corner_normals[loop_index].vector)

    return Vector(mesh.loops[loop_index].normal)


def _resolve_surface_for_triangle(
        mesh_obj,
        triangle,
        material_slots: list,
        material_vg_indices: dict[int, int]) -> int:

    slot_count = len(material_slots)
    polygon_index = getattr(triangle, "polygon_index", None)

    if material_vg_indices and polygon_index is not None:

        polygon = mesh_obj.data.polygons[polygon_index]

        for vert_idx in polygon.vertices:

            vertex = mesh_obj.data.vertices[vert_idx]

            for group_element in vertex.groups:

                if (group_element.group in material_vg_indices
                        and group_element.weight > 0.0):

                    return material_vg_indices[group_element.group]

    material_index = int(triangle.material_index)

    if 0 <= material_index < slot_count:

        return material_index

    return 0


def build_geometry(mesh_obj) -> GeometryBuild:
    """Build VMSH + SUBM with per-surface vertex ranges and shared vertices."""

    if mesh_obj is None or mesh_obj.type != "MESH":

        raise ValueError("A mesh object is required for export")

    mesh = mesh_obj.data
    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
    vertex_transform, normal_transform = _vertex_and_normal_transforms(
        mesh_obj)
    use_vertex_normals = (
        not getattr(mesh, "has_custom_normals", False)
        and _faces_are_all_sharp(mesh)
    )
    material_slots = list(mesh.materials)
    material_vg_indices: dict[int, int] = {}

    for surface_index, slot in enumerate(material_slots):

        if slot is None:

            continue

        for vg_idx, vg in enumerate(mesh_obj.vertex_groups):

            if vg.name == slot.name:

                material_vg_indices[vg_idx] = surface_index
                break

    surface_triangles: dict[int, list] = {}

    for triangle in mesh.loop_triangles:

        surface = _resolve_surface_for_triangle(
            mesh_obj,
            triangle,
            material_slots,
            material_vg_indices,
        )
        surface_triangles.setdefault(surface, []).append(triangle)

    if not surface_triangles:

        raise ValueError("Mesh has no triangles to export")

    vertices: list[Vector] = []
    normals: list[Vector] = []
    uvs: list[Vector] = []
    ordered_indices: list[int] = []
    source_vertex_indices: list[int] = []
    sub_mesh_infos: list[dict] = []

    for surface_index in sorted(surface_triangles.keys()):

        triangles = surface_triangles[surface_index]
        first_vertex = len(vertices)
        indices_start = len(ordered_indices)
        surface_indices: list[int] = []
        vertex_cache: dict[tuple, int] = {}

        for triangle in triangles:

            tri_indices: list[int] = []

            for loop_index in triangle.loops:

                loop = mesh.loops[loop_index]
                vert = mesh.vertices[loop.vertex_index]
                position = blender_to_vision(
                    vertex_transform @ Vector(vert.co))
                normal = Vector(
                    normal_transform @ _loop_export_normal(
                        mesh,
                        loop_index,
                        loop.vertex_index,
                        use_vertex_normals,
                    )
                )

                if normal.length_squared > 0.0:

                    normal.normalize()

                if uv_layer is not None:

                    uv = Vector((
                        uv_layer[loop_index].uv[0],
                        uv_layer[loop_index].uv[1],
                    ))

                else:

                    uv = Vector((0.0, 0.0))

                key = (
                    round(position.x, 4),
                    round(position.y, 4),
                    round(position.z, 4),
                    round(normal.x, 4),
                    round(normal.y, 4),
                    round(normal.z, 4),
                    round(uv.x, 6),
                    round(uv.y, 6),
                )

                if key in vertex_cache:

                    tri_indices.append(vertex_cache[key])

                else:

                    idx = len(vertices)
                    vertex_cache[key] = idx
                    tri_indices.append(idx)
                    vertices.append(position)
                    normals.append(normal)
                    uvs.append(uv)
                    source_vertex_indices.append(int(loop.vertex_index))

            surface_indices.extend(tri_indices)

        ordered_indices.extend(surface_indices)
        sub_mesh_infos.append({
            "surface_index": surface_index,
            "indices_start": indices_start,
            "indices_count": len(surface_indices),
            "first_vertex": first_vertex,
            "num_vertices": len(vertices) - first_vertex,
        })

    mesh_bounds = bounding_box_from_points(vertices)
    sub_meshes = VisSubMeshChunk()
    sub_meshes.unknown = -1
    sub_meshes.version = 3
    sub_meshes.geometry_info = []
    sub_meshes.meshes = []

    for info in sub_mesh_infos:

        buffer = VisMeshBuffer_cl()
        buffer.format_version = 3
        buffer.geometry_info_count = 0
        buffer.indices_start = info["indices_start"]
        buffer.indices_count = info["indices_count"]
        buffer.first_vertex = info["first_vertex"]
        buffer.num_vertices = info["num_vertices"]
        buffer.local_bounds = mesh_bounds
        buffer.surface_index = info["surface_index"]
        buffer.geometry_index = -1
        sub_meshes.meshes.append(buffer)

    vmsh = VMshChunk()
    vmsh.chunk_id = VisChunkId.VMSH
    vmsh.loader_version = VMshChunk.LOADER_VERSION
    vmsh.version = VMshChunk.LOCAL_VERSION
    vmsh.descriptor = make_vertex_descriptor()
    vmsh.usage_flag_vertices = 0
    vmsh.bind_flag_vertices = 0
    vmsh.mesh_data_is_big_endian = False
    vmsh.unused_1 = 0
    vmsh.prim_type = VisPrimitiveType.INDEXED_TRILIST
    vmsh.index_format = VisIndexFormat._16
    vmsh.mem_usage_flag_indices = 0
    vmsh.bind_flag_indices = 0
    vmsh.vertices_double_buffered = 1
    vmsh.indices_double_buffered = 1
    vmsh.double_buffering_from_file = 0
    vmsh.use_projection = 1
    vmsh.texture_channels_count = 0
    vmsh.texture_channel_paths = []
    vmsh.render_state = VisRenderState()
    vmsh.render_state.transp_mode = VisTransparencyType.NONE
    vmsh.render_state.unused = 0
    vmsh.render_state.render_flags = _DEFAULT_RENDER_FLAGS
    vmsh.effect_config = VisEffectConfig_cl()
    vmsh.effect_config.values = []
    vmsh.bounding_box = mesh_bounds
    vmsh.unused = 0
    vmsh.vertices = vertices
    vmsh.normals = normals
    vmsh.uvs = uvs
    vmsh.indices = ordered_indices
    vmsh.faces = [
        ordered_indices[i: i + 3]
        for i in range(0, len(ordered_indices), 3)
    ]
    vmsh.vertex_count = len(vertices)
    vmsh.index_count = len(ordered_indices)
    vmsh.current_prim_count = len(ordered_indices) // 3

    if ordered_indices and max(ordered_indices) > 0xFFFF:

        vmsh.index_format = VisIndexFormat._32

    return GeometryBuild(vmsh, sub_meshes, source_vertex_indices)
