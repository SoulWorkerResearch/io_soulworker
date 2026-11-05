from __future__ import annotations

from dataclasses import dataclass
from json import loads
from pathlib import Path

from mathutils import Matrix, Vector

from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.subm_chunk import VisMeshBuffer_cl, VisSubMeshChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.vis_bounding_box import HavokBoundingBox
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_index_format import VisIndexFormat
from io_soulworker.core.vis_lighting_method import VisLightingMethod
from io_soulworker.core.vis_material_lighting import VisMaterialLighting
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
from io_soulworker.file_import.resource_path import (
    game_relative_texture_path,
    resolve_resource_path,
)
from io_soulworker.core.materials_xml.shader_param_string import (
    ShaderParamString, paramstring_from_params,
)
from io_soulworker.core.shader_lib import parse_shader_lib_file
from io_soulworker.file_import.model.chunk_reader import ModelChunkReader
from io_soulworker.file_import.shaders.node_groups import (
    collect_shader_from_material,
)
from io_soulworker.unit_scale import blender_to_vision


_POS_OFFSET = 0x3000
_NORMAL_OFFSET = 0x300C
_TEX0_OFFSET = 0x2018

EXPORT_VMSH_VERSION = 1
"""Every shipped SoulWorker mesh is VMSH version 1 with ``TRILIST`` plus an
index buffer; newer layouts load too but differ from the originals."""

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


def _vertex_and_normal_transforms(obj, transform: Matrix | None = None):

    vertex_transform = transform if transform is not None else obj.matrix_world.to_3x3()

    try:

        normal_transform = vertex_transform.to_3x3().inverted().transposed()

    except ValueError:

        normal_transform = vertex_transform.to_3x3().copy()

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

    return ""


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
        resources_root: Path | None = None,
        *, source_material=None,
        source_directory: Path | None = None) -> MaterialSidecar:

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
    source_shader = getattr(source_material, "shader", None)
    source_root = resources_root or material.get(
        "soulworker_resources_root", "")
    if not source_root and source_directory is not None:
        source_root = next((parent for parent in source_directory.parents
                            if (parent / 'Shaders').is_dir()
                            and (parent / 'Character').is_dir()), None)
    library_path = material.get("soulworker_shader_library_path", "")
    if not library_path and source_shader is not None and source_directory is not None:
        library = resolve_resource_path(
            source_directory, source_shader.library)
        if library is not None:
            library_path = str(library)

    stored_effect = material.get("soulworker_shader_effect", "")
    if shader is None and (stored_effect or source_shader is not None):
        params = ShaderParamString(
            material.get("soulworker_shader_paramstring", "")
            if stored_effect else source_shader.paramstring.to_string())
        effect_name = stored_effect or source_shader.effect
        library_name = material.get("soulworker_shader_library", "")
        if not library_name and source_shader is not None:
            library_name = Path(source_shader.library.replace('\\', '/')).stem
        if source_root:
            for name, value in params.items():
                resolved = resolve_resource_path(source_root, value)
                if resolved is not None:
                    params[name] = str(resolved)
        paramstring = params.to_string()
        if library_path and Path(library_path).is_file():
            effect = parse_shader_lib_file(
                Path(library_path)).effects.get(effect_name)
            if effect is not None:
                paramstring = paramstring_from_params(effect.params, params)
        shader = (library_name, effect_name, paramstring)

    stored_diffuse = material.get("soulworker_diffuse") or ""
    stored_specular = material.get("soulworker_specular") or ""
    stored_normal = material.get("soulworker_normal") or ""

    def stored_texture(raw: str) -> str:
        directory = source_directory or material.get(
            "soulworker_source_directory", "")
        if directory and raw:
            resolved = resolve_resource_path(directory, raw)
            if resolved is None:
                resolved = resolve_resource_path(
                    directory, 'Textures/' + Path(raw.replace('\\', '/')).name)
            if resolved is not None:
                return str(resolved)
        # Some original MTRS paths still point into the author's _Graphic
        # tree. Recover by basename only when the unpacked tree has one match.
        if source_root and raw:
            name = Path(raw.replace('\\', '/')).name
            matches = (path for path in Path(
                source_root).rglob(name) if path.is_file())
            first = next(matches, None)
            if first is not None and next(matches, None) is None:
                resolved = resolve_resource_path(
                    source_root, str(first.relative_to(source_root)))
                if resolved is not None:
                    return str(resolved)
        return raw

    sidecar = MaterialSidecar(
        name=material.get("soulworker_material_name")
        or material.name or "material",
        diffuse=_diffuse_from_blender_material(
            material,
            resources_root,
        ) or stored_texture(stored_diffuse) or DEFAULT_DIFFUSE,
        specular=specular_map or stored_texture(stored_specular),
        normal=_named_image_path(
            material,
            "Normal",
            resources_root,
        ) or stored_texture(stored_normal),
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
        sidecar.shader_library_path = library_path

    _apply_stored_surface(sidecar, material)

    return sidecar


def _stored_json(material, key: str) -> dict:

    raw = material.get(key)

    if not raw:

        return {}

    try:

        value = loads(raw)

    except (TypeError, ValueError):

        return {}

    return value if isinstance(value, dict) else {}


def _xml_bool(raw, default: bool) -> bool:

    if raw is None:

        return default

    return str(raw).strip().upper() == "TRUE"


_LIGHTING_BY_METHOD = {
    int(VisLightingMethod.FULLBRIGHT): VisMaterialLighting.NONE.value,
    int(VisLightingMethod.LIGHTMAPPING): VisMaterialLighting.LIGHTMAPPING.value,
    int(VisLightingMethod.LIGHTGRID): VisMaterialLighting.LIGHT_GRID.value,
}


def _apply_stored_surface(sidecar: MaterialSidecar, material) -> None:
    """Prefer surface fields captured at import over node-tree heuristics.

    Blender has no notion of Vision transparency modes, alpha thresholds,
    ambient colour or surface flags, so a material that came from a .model
    keeps the values it was imported with. Edit the ``soulworker_mtrs`` /
    ``soulworker_material_xml`` custom properties to change them.
    """

    stored_mtrs = _stored_json(material, "soulworker_mtrs")
    stored_xml = _stored_json(material, "soulworker_material_xml")

    if stored_mtrs:

        try:

            sidecar.transparency = VisTransparencyType(
                int(stored_mtrs.get(
                    "transparency_type", int(sidecar.transparency))))

        except ValueError:

            pass

        sidecar.alphathreshold = float(stored_mtrs.get(
            "custom_alpha_threshold", sidecar.alphathreshold))
        sidecar.spec_mul = float(stored_mtrs.get("spec_mul", sidecar.spec_mul))
        sidecar.spec_exp = float(stored_mtrs.get("spec_exp", sidecar.spec_exp))
        sidecar.parallax_scale = float(stored_mtrs.get(
            "parallax_scale", sidecar.parallax_scale))
        sidecar.parallax_bias = float(stored_mtrs.get(
            "parallax_bias", sidecar.parallax_bias))
        sidecar.sorting_key = int(stored_mtrs.get(
            "ui_sorting_key", sidecar.sorting_key))
        sidecar.user_flags = int(stored_mtrs.get(
            "user_flags", sidecar.user_flags))
        sidecar.lighting = _LIGHTING_BY_METHOD.get(
            int(stored_mtrs.get("lighting_method", 0)), sidecar.lighting)

        ambient = stored_mtrs.get("ambient_color")

        if isinstance(ambient, (list, tuple)) and len(ambient) == 4:

            sidecar.ambient = tuple(int(component) for component in ambient)

        sidecar.mtrs_fields = stored_mtrs

    if stored_xml:

        sidecar.doublesided = _xml_bool(
            stored_xml.get("doublesided"), sidecar.doublesided)
        sidecar.depthwrite = _xml_bool(
            stored_xml.get("depthwrite"), sidecar.depthwrite)

        if stored_xml.get("Lighting"):

            sidecar.lighting = str(stored_xml["Lighting"])

        sidecar.xml_attributes = stored_xml


def build_material_sidecars(
        mesh_obj,
        resources_root: Path | None = None) -> list[MaterialSidecar]:

    slots = list(mesh_obj.data.materials)

    if not slots:

        return [MaterialSidecar(name="default")]

    source = mesh_obj.data.get("soulworker_source_path", "")
    if not source:
        # Recover pre-metadata imports only when an image and its stored
        # relative filename identify an existing source model unambiguously.
        for material in slots:
            if material is None or material.node_tree is None:
                continue
            relative = Path((material.get("soulworker_diffuse")
                            or "").replace('\\', '/'))
            if relative.is_absolute() or '..' in relative.parts or not relative.parts:
                continue
            for node in material.node_tree.nodes:
                image = getattr(node, 'image', None)
                if image is None:
                    continue
                path = Path(image.filepath)
                if tuple(part.lower() for part in path.parts[-len(relative.parts):]) != tuple(
                        part.lower() for part in relative.parts):
                    continue
                for _ in relative.parts:
                    path = path.parent
                candidate = path / (mesh_obj.data.name + '.model')
                if candidate.is_file():
                    source = str(candidate)
                    break
            if source:
                break
    overrides = {}
    source_directory = None
    if source and Path(source).is_file():
        reader = ModelChunkReader(Path(source))
        reader.run()
        overrides = reader.xml_materials
        source_directory = Path(source).parent

    result = []
    for slot in slots:
        source_material = None
        if slot is not None:
            name = slot.get("soulworker_material_name", slot.name)
            source_material = overrides.get(name)
            base, separator, suffix = name.rpartition('.')
            if source_material is None and separator and suffix.isdigit():
                source_material = overrides.get(base)
        result.append(material_sidecar_from_blender(
            slot, resources_root, source_material=source_material,
            source_directory=source_directory,
        ))
    return result


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


def build_geometry(mesh_obj, *, transform: Matrix | None = None) -> GeometryBuild:
    """Build VMSH + SUBM with per-surface vertex ranges and shared vertices."""

    if mesh_obj is None or mesh_obj.type != "MESH":

        raise ValueError("A mesh object is required for export")

    mesh = mesh_obj.data
    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
    vertex_transform, normal_transform = _vertex_and_normal_transforms(
        mesh_obj, transform)
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
    vmsh.version = EXPORT_VMSH_VERSION
    vmsh.descriptor = make_vertex_descriptor()
    vmsh.usage_flag_vertices = 0
    vmsh.bind_flag_vertices = 0
    vmsh.mesh_data_is_big_endian = False
    vmsh.unused_1 = 0
    vmsh.prim_type = VisPrimitiveType.TRILIST
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
