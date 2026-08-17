from __future__ import annotations

import json
from logging import debug, error, info, warning
from pathlib import Path

import bpy
from bpy.types import Image, Material, Node, NodeTree, ShaderNodeGroup

from io_soulworker.core.materials_xml.shader_tag import ShaderTag
from io_soulworker.core.shader_lib import (
    ShaderEffect,
    ShaderLibrary,
    ShaderParamComment,
    scan_shader_libs,
)

NODE_GROUP_PREFIX = "SW."
_PARAMS_KEY = "soulworker_params"
_TEXTURE_TYPES = frozenset({"texture", "cubemap"})


def library_stem_from_path(library: str) -> str:
    """Normalize a materials.xml library attribute to a ShaderLib stem."""

    cleaned = library.replace("\\", "/").strip().lstrip("/")

    return Path(cleaned).stem


def node_group_name(library_stem: str, effect_name: str) -> str:

    return f"{NODE_GROUP_PREFIX}{library_stem}.{effect_name}"


def _resources_root() -> Path | None:

    scene = bpy.context.scene if bpy.context else None
    root_raw = getattr(scene, "soulworker_unpack_resources",
                       "") if scene else ""
    root_raw = (root_raw or "").strip()

    if not root_raw:

        return None

    root = Path(bpy.path.abspath(root_raw)).resolve()

    if not root.is_dir():

        return None

    return root


def _resolve_resource_file(relative: str) -> Path | None:

    root = _resources_root()

    if root is None or not relative.strip():

        return None

    candidate = root / relative.replace("\\", "/").lstrip("/")

    if candidate.is_file():

        return candidate

    return None


def _load_resource_image(relative: str) -> Image | None:

    path = _resolve_resource_file(relative)

    if path is None:

        error("Texture not found under resources root: %s", relative)
        return None

    debug("load shader texture: %s", path)

    return bpy.data.images.load(str(path), check_existing=True)


def _parse_floats(raw: str) -> list[float]:

    if not raw.strip():

        return []

    values: list[float] = []

    for part in raw.split(","):

        token = part.strip()

        if token == "":

            continue

        try:

            values.append(float(token))

        except ValueError:

            return []

    return values


def _socket_type_for_param(param: ShaderParamComment) -> str | None:

    match param.value_type:

        case "float":
            return "NodeSocketFloat"

        case "int":
            return "NodeSocketInt"

        case "float2" | "float3":
            if param.ui == "color":
                return "NodeSocketColor"
            return "NodeSocketVector"

        case "float4":
            return "NodeSocketColor"

        case "texture" | "cubemap":
            # Color input; Image / Environment Texture nodes link into it.
            return "NodeSocketColor"

        case "float4x4":
            return None

        case _:
            warning(
                "Unsupported ShaderLib param type %s for %s",
                param.value_type,
                param.name,
            )
            return None


def _default_for_socket(param: ShaderParamComment, socket_type: str):

    if param.value_type in _TEXTURE_TYPES:

        return [1.0, 1.0, 1.0, 1.0]

    values = _parse_floats(param.default) if param.default else []

    match socket_type:

        case "NodeSocketFloat":
            return values[0] if values else 0.0

        case "NodeSocketInt":
            return int(values[0]) if values else 0

        case "NodeSocketVector":
            return (values + [0.0, 0.0, 0.0])[:3]

        case "NodeSocketColor":
            if len(values) >= 4:
                return values[:4]
            if len(values) == 3:
                return [*values, 1.0]
            if len(values) == 1:
                return [values[0], values[0], values[0], 1.0]
            return [0.0, 0.0, 0.0, 1.0]

    return None


def _clear_interface(node_tree: NodeTree) -> None:

    for item in list(node_tree.interface.items_tree):

        node_tree.interface.remove(item)


def _add_param_sockets(node_tree: NodeTree, param: ShaderParamComment) -> None:

    if param.value_type == "float4x4":

        for row_index in range(4):

            socket = node_tree.interface.new_socket(
                name=f"{param.name}_r{row_index}",
                in_out="INPUT",
                socket_type="NodeSocketVector",
            )
            socket.description = param.description
            socket.default_value = [0.0, 0.0, 0.0]

        return

    socket_type = _socket_type_for_param(param)

    if socket_type is None:

        return

    socket = node_tree.interface.new_socket(
        name=param.name,
        in_out="INPUT",
        socket_type=socket_type,
    )
    socket.description = param.description

    default = _default_for_socket(param, socket_type)

    if default is not None:

        socket.default_value = default


def _texture_node_type(value_type: str) -> str:

    if value_type == "cubemap":

        return "ShaderNodeTexEnvironment"

    return "ShaderNodeTexImage"


def _store_param_metadata(node_tree: NodeTree, effect: ShaderEffect) -> None:

    payload = [
        {
            "name": param.name,
            "description": param.description,
            "default": param.default,
            "value_type": param.value_type,
            "ui": param.ui,
        }
        for param in effect.params
    ]

    node_tree[_PARAMS_KEY] = json.dumps(payload)


def _load_param_metadata(node_tree: NodeTree) -> list[ShaderParamComment]:

    raw = node_tree.get(_PARAMS_KEY)

    if not raw:

        return []

    try:

        payload = json.loads(raw)

    except (TypeError, json.JSONDecodeError):

        return []

    return [
        ShaderParamComment(
            name=item["name"],
            description=item.get("description", ""),
            default=item.get("default", ""),
            value_type=item.get("value_type", "float"),
            ui=item.get("ui", "none"),
        )
        for item in payload
    ]


def ensure_effect_node_group(
        library: ShaderLibrary,
        effect: ShaderEffect) -> NodeTree:
    """Create or refresh a parameter-only shader node group for an EFFECT."""

    name = node_group_name(library.stem, effect.name)
    node_tree = bpy.data.node_groups.get(name)

    if node_tree is None:

        node_tree = bpy.data.node_groups.new(name, "ShaderNodeTree")

    _clear_interface(node_tree)

    for param in effect.params:

        _add_param_sockets(node_tree, param)

    nodes = node_tree.nodes
    nodes.clear()
    nodes.new("NodeGroupInput")
    nodes.new("NodeGroupOutput")

    node_tree["soulworker_library"] = library.stem
    node_tree["soulworker_effect"] = effect.name
    _store_param_metadata(node_tree, effect)

    return node_tree


def sync_shader_node_groups(resources_root_raw: str) -> int:
    """Scan Shaders/*.ShaderLib under the resources root and build node groups."""

    root_raw = (resources_root_raw or "").strip()

    if not root_raw:

        debug("No SoulWorker resources root; skip ShaderLib sync")
        return 0

    root = Path(bpy.path.abspath(root_raw)).resolve()

    if not root.is_dir():

        error("SoulWorker resources root is not a directory: %s", root)
        return 0

    libraries = scan_shader_libs(root)
    count = 0

    for library in libraries:

        for effect in library.effects.values():

            ensure_effect_node_group(library, effect)
            count += 1

    info(
        "Synced %d shader effect node groups from %d ShaderLib files in %s",
        count,
        len(libraries),
        root / "Shaders",
    )

    return count


def find_effect_node_group(library: str, effect: str) -> NodeTree | None:

    return bpy.data.node_groups.get(
        node_group_name(library_stem_from_path(library), effect)
    )


def _set_texture_on_material(
    material_tree: NodeTree,
    group_node: Node,
    param: ShaderParamComment,
    relative: str,
) -> Node:

    tex_node = material_tree.nodes.get(param.name)

    if tex_node is None or tex_node.bl_idname not in {
        "ShaderNodeTexImage",
        "ShaderNodeTexEnvironment",
    }:

        tex_node = material_tree.nodes.new(
            _texture_node_type(param.value_type))
        tex_node.name = param.name

    tex_node.label = param.name
    tex_node.width = 240.0
    tex_node.image = _load_resource_image(relative)

    color_out = tex_node.outputs.get("Color")
    color_in = group_node.inputs.get(param.name)

    if color_out is not None and color_in is not None:

        for link in list(color_in.links):

            material_tree.links.remove(link)

        material_tree.links.new(color_out, color_in)

    return tex_node


def _set_input_value(
    node: Node,
    material_tree: NodeTree,
    input_name: str,
    raw: str,
    param: ShaderParamComment | None,
) -> None:

    if param is not None and param.value_type in _TEXTURE_TYPES:

        _set_texture_on_material(material_tree, node, param, raw)
        return

    socket = node.inputs.get(input_name)

    if socket is None:

        return

    values = _parse_floats(raw)
    socket_id = socket.bl_idname

    if "Float" in socket_id:

        if values:
            socket.default_value = values[0]
        return

    if "Int" in socket_id:

        if values:
            socket.default_value = int(values[0])
        return

    if "Vector" in socket_id:

        socket.default_value = (values + [0.0, 0.0, 0.0])[:3]
        return

    if "Color" in socket_id:

        if len(values) >= 4:
            socket.default_value = values[:4]
        elif len(values) == 3:
            socket.default_value = [*values, 1.0]
        elif len(values) == 1:
            socket.default_value = [values[0], values[0], values[0], 1.0]


def arrange_material_nodes(node_tree: NodeTree) -> None:
    """Place material nodes in columns so they do not overlap."""

    nodes = list(node_tree.nodes)

    if not nodes:

        return

    image_types = {"ShaderNodeTexImage", "ShaderNodeTexEnvironment"}
    images = [n for n in nodes if n.bl_idname in image_types]
    groups = [n for n in nodes if n.bl_idname == "ShaderNodeGroup"]
    bsdfs = [n for n in nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"]
    outputs = [n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
    known = set(images) | set(groups) | set(bsdfs) | set(outputs)
    others = [n for n in nodes if n not in known]

    def _stack(
            column_nodes: list[Node],
            origin_x: float,
            gap: float = 40.0) -> float:
        """Layout a vertical stack; return column width used."""

        y = 0.0
        width = 0.0

        for node in column_nodes:

            node.location = (origin_x, y)
            width = max(width, float(node.width))
            # dimensions.y is often 0 until drawn; use a stable estimate.
            height = max(float(getattr(node, "height", 0.0) or 0.0), 280.0)
            if node.bl_idname == "ShaderNodeGroup":
                height = max(height, 120.0 + 22.0 * max(len(node.inputs), 1))
            y -= height + gap

        return width

    x = -900.0
    x += _stack(images, x) + 80.0
    x += _stack(groups, x) + 80.0
    x += _stack(others, x) + 80.0
    x += _stack(bsdfs, x) + 80.0
    _stack(outputs, x)


def apply_shader_to_material(
        material: Material,
        shader: ShaderTag) -> Node | None:
    """Add the EFFECT node group to a material and fill PARAMCOMMENT values."""

    node_tree = material.node_tree

    if node_tree is None:

        error("Material %s has no node tree", material.name)
        return None

    group_tree = find_effect_node_group(shader.library, shader.effect)

    if group_tree is None:

        warning(
            "Missing shader node group for library=%s effect=%s",
            shader.library,
            shader.effect,
        )
        return None

    group_node: ShaderNodeGroup = node_tree.nodes.new("ShaderNodeGroup")
    group_node.node_tree = group_tree
    group_node.name = shader.effect
    group_node.label = shader.effect
    group_node.width *= 3.0

    params_by_name = {
        param.name: param for param in _load_param_metadata(group_tree)}

    for name, raw in shader.paramstring.items():

        param = params_by_name.get(name)

        if param is None:

            continue

        if param.value_type == "float4x4":

            values = _parse_floats(raw)

            for row_index in range(4):

                start = row_index * 4
                row = (values[start: start + 4] + [0.0, 0.0, 0.0])[:3]
                socket = group_node.inputs.get(f"{name}_r{row_index}")

                if socket is not None:

                    socket.default_value = row

            continue

        _set_input_value(group_node, node_tree, name, raw, param)

    return group_node
