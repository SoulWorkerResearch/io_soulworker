from mathutils import Vector

from io_soulworker.chunks.expr_chunk import ExprChunk
from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.subm_chunk import VisMeshBuffer_cl, VisSubMeshChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.vis_bounding_box import HavokBoundingBox
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_color import VisColor
from io_soulworker.core.vis_index_format import VisIndexFormat
from io_soulworker.core.vis_material_effect import VisMaterialEffect
from io_soulworker.core.vis_mesh_effect_config import VisEffectConfig_cl
from io_soulworker.core.vis_prim_type import VisPrimitiveType
from io_soulworker.core.vis_render_state import VisRenderState
from io_soulworker.core.vis_render_state_flags import VisRenderStateFlag
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.core.vis_vertex_descriptor import VisMBVertexDescriptor_cl
from io_soulworker.unit_scale import blender_to_vision


# Descriptor flags observed in shipped static meshes (pos/normal float3, uv float2).
_POS_OFFSET = 0x3000
_NORMAL_OFFSET = 0x300C
_TEX0_OFFSET = 0x2018
_MISSING = 0xFFFF

_DEFAULT_DIFFUSE = r"\PlainWhite.DDS"

_DEFAULT_RENDER_FLAGS = (
    VisRenderStateFlag.FRONTFACE
    | VisRenderStateFlag.FILTERING
    | VisRenderStateFlag.USEADDITIVEALPHA
)


class VmeshExportData:
    """Serializable payload for a static .vmesh file."""

    def __init__(
        self,
        mesh: VMshChunk,
        materials: list[MtrsChunk],
        sub_meshes: VisSubMeshChunk,
        export_transform: ExprChunk,
    ) -> None:

        self.mesh = mesh
        self.materials = materials
        self.sub_meshes = sub_meshes
        self.export_transform = export_transform


def _bounding_box_from_points(points: list[Vector]) -> HavokBoundingBox:

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


def _make_vertex_descriptor() -> VisMBVertexDescriptor_cl:

    descriptor = VisMBVertexDescriptor_cl()
    descriptor.header_size = 48
    descriptor.stride = 32
    descriptor.pos_offset = _POS_OFFSET
    descriptor.normal_offset = _NORMAL_OFFSET
    descriptor.tex_offset[0] = _TEX0_OFFSET
    descriptor.first_text_coord = 255

    return descriptor


def _make_default_material(name: str, diffuse_map: str) -> MtrsChunk:

    material = MtrsChunk()
    material._envelope_enter_depth = 1
    material.version = 6
    material.name = name or "default"
    material.flags = 0
    material.ui_sorting_key = 0
    material.spec_mul = 0.0
    material.spec_exp = 1.0
    material.transparency_type = VisTransparencyType.NONE
    material.ui_deferred_id = 0
    material.depth_bias = 0.0
    material.depth_bias_clamp = 0.0
    material.slope_scaled_depth_bias = 0.0
    material.diffuse_map = diffuse_map or _DEFAULT_DIFFUSE
    material.specular_map = ""
    material.normal_map = ""
    material.aux_texture_paths = []
    material.user_data = ""
    material.user_flags = 0
    material.ambient_color = VisColor(0, 0, 0, 255)
    material.brightness = 0
    material.light_color = VisColor(0, 0, 0, 0)
    material.parallax_scale = 0.0
    material.parallax_bias = 0.0
    material.config_effects = [VisMaterialEffect()]
    material.override_library = ""
    material.override_material = ""
    material.ui_mobile_shader_flags = 0

    return material


def _diffuse_from_blender_material(material) -> str:

    if material is None or not material.use_nodes or material.node_tree is None:

        return _DEFAULT_DIFFUSE

    for node in material.node_tree.nodes:

        if node.type != "TEX_IMAGE":

            continue

        image = getattr(node, "image", None)

        if image is None or not image.filepath:

            continue

        # Keep a game-style relative path when possible; otherwise basename.
        path = image.filepath

        if path.startswith("//"):

            path = path[2:]

        path = path.replace("/", "\\")

        return path if path else _DEFAULT_DIFFUSE

    return _DEFAULT_DIFFUSE


def _vertex_and_normal_transforms(obj):

    vertex_transform = obj.matrix_world.to_3x3()

    try:

        normal_transform = vertex_transform.inverted().transposed()

    except ValueError:

        normal_transform = vertex_transform.copy()

    return vertex_transform, normal_transform


def build_vmesh_from_blender_object(obj) -> VmeshExportData:
    """Build Vision static-mesh chunks from a Blender MESH object."""

    if obj is None or obj.type != "MESH":

        raise ValueError("A mesh object is required for .vmesh export")

    mesh = obj.data
    mesh.calc_loop_triangles()

    if hasattr(mesh, "calc_normals_split"):

        mesh.calc_normals_split()

    uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
    vertex_transform, normal_transform = _vertex_and_normal_transforms(obj)

    vertices: list[Vector] = []
    normals: list[Vector] = []
    uvs: list[Vector] = []
    indices: list[int] = []

    # material_index -> list of triangle corner vertex indices (into vertices[])
    material_triangles: dict[int, list[int]] = {}

    for triangle in mesh.loop_triangles:

        material_index = int(triangle.material_index)
        tri_indices: list[int] = []

        for loop_index in triangle.loops:

            loop = mesh.loops[loop_index]
            vert = mesh.vertices[loop.vertex_index]

            position = blender_to_vision(vertex_transform @ Vector(vert.co))
            normal = Vector(normal_transform @ loop.normal)

            if normal.length_squared > 0.0:

                normal.normalize()

            if uv_layer is not None:

                uv = Vector((uv_layer[loop_index].uv[0],
                            uv_layer[loop_index].uv[1]))

            else:

                uv = Vector((0.0, 0.0))

            tri_indices.append(len(vertices))
            vertices.append(position)
            normals.append(normal)
            uvs.append(uv)

        material_triangles.setdefault(material_index, []).extend(tri_indices)
        indices.extend(tri_indices)

    if not vertices:

        raise ValueError("Mesh has no triangles to export")

    materials: list[MtrsChunk] = []
    slots = list(mesh.materials)

    if not slots:

        materials.append(_make_default_material("default", _DEFAULT_DIFFUSE))
        material_triangles = {0: indices.copy()}

    else:

        used_indices = sorted(material_triangles.keys())
        remap = {old: new for new, old in enumerate(used_indices)}
        remapped: dict[int, list[int]] = {}

        for old_index, tri in material_triangles.items():

            remapped[remap[old_index]] = tri

        material_triangles = remapped

        for old_index in used_indices:

            blender_material = slots[old_index] if old_index < len(
                slots) else None
            name = blender_material.name if blender_material else f"material_{old_index}"
            diffuse = _diffuse_from_blender_material(blender_material)
            materials.append(_make_default_material(name, diffuse))

    # Rebuild a contiguous index buffer ordered by material for SUBM ranges.
    ordered_indices: list[int] = []
    sub_meshes = VisSubMeshChunk()
    sub_meshes.unknown = -1
    sub_meshes.version = 3
    sub_meshes.geometry_info = []
    sub_meshes.meshes = []

    mesh_bounds = _bounding_box_from_points(vertices)

    for surface_index in range(len(materials)):

        surface_indices = material_triangles.get(surface_index, [])
        start = len(ordered_indices)
        ordered_indices.extend(surface_indices)

        buffer = VisMeshBuffer_cl()
        buffer.format_version = 3
        buffer.geometry_info_count = 0
        buffer.indices_start = start
        buffer.indices_count = len(surface_indices)
        buffer.first_vertex = 0
        buffer.num_vertices = len(vertices)
        buffer.local_bounds = mesh_bounds
        buffer.surface_index = surface_index
        buffer.geometry_index = -1
        sub_meshes.meshes.append(buffer)

    vmsh = VMshChunk()
    vmsh.chunk_id = VisChunkId.VMSH
    vmsh.loader_version = VMshChunk.LOADER_VERSION
    vmsh.version = 1
    vmsh.descriptor = _make_vertex_descriptor()
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

    expr = ExprChunk()
    expr.version = ExprChunk.LOCAL_VERSION
    expr.flag = 1

    return VmeshExportData(vmsh, materials, sub_meshes, expr)
