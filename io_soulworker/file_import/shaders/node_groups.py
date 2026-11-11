from __future__ import annotations

import json
from dataclasses import dataclass
from logging import debug, error, info, warning
from math import copysign, inf, isfinite
from pathlib import Path
from struct import pack, unpack

import bpy
from bpy.types import Image, Material, Node, NodeTree, ShaderNodeGroup

from ...core.materials_xml.shader_param_string import (
    ShaderParamString,
    format_param_float,
    paramstring_from_params,
    paramstring_in_source_order,
)
from ...core.materials_xml.shader_tag import ShaderTag
from ...core.shader_lib import (
    ShaderEffect,
    ShaderLibrary,
    ShaderParamComment,
    scan_shader_libs,
)
from ...file_import.resource_path import (
    game_relative_texture_path,
    load_blender_image,
    resolve_resource_path,
)

NODE_GROUP_PREFIX = "SW."
_PARAMS_KEY = "soulworker_params"
_TEXTURE_TYPES = frozenset({"texture", "cubemap"})


VISION_BUILTIN_LIBRARIES = {
    "vmaterial", "vmaterialglow", "vmaterialrim", "vmaterialfullbright",
    "vdeferredmaterial", "vmaterialparallax", "vmaterialdecal",
}
"""ShaderLibs shipped inside the engine (Shared.zip as .Shaderbin only).

Their sources are not part of the unpacked game tree, so no node group can be
synced for them; the plain Principled BSDF already approximates them.
"""

_reported_missing_effects: set[tuple[str, str]] = set()


def _report_missing_effect(library: str, effect: str) -> None:
    """Log a missing EFFECT once per library/effect pair."""

    key = (library_stem_from_path(library).lower(), effect)

    if key in _reported_missing_effects:

        return

    _reported_missing_effects.add(key)

    if key[0] in VISION_BUILTIN_LIBRARIES:

        debug("Built-in Vision shader without node group: %s/%s",
              library, effect)
        return

    warning("Missing shader node group for library=%s effect=%s",
            library, effect)


def library_stem_from_path(library: str) -> str:
    """Normalize a materials.xml library attribute to a ShaderLib stem."""

    cleaned = library.replace("\\", "/").strip().lstrip("/")

    return Path(cleaned).stem


def node_group_name(library_stem: str, effect_name: str) -> str:

    return f"{NODE_GROUP_PREFIX}{library_stem}.{effect_name}"


def _resources_root(explicit: Path | str | None = None) -> Path | None:
    """Unpacked resources root: the explicit one, else the N-panel setting."""

    if explicit:

        root = Path(explicit)

        if root.is_dir():

            return root.resolve()

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


def _resolve_resource_file(
        relative: str,
        resources_root: Path | str | None = None) -> Path | None:

    root = _resources_root(resources_root)

    if root is None or not relative.strip():

        return None

    return resolve_resource_path(root, relative)


def _load_resource_image(
        relative: str,
        resources_root: Path | str | None = None) -> Image | None:

    path = _resolve_resource_file(relative, resources_root)

    if path is None:

        error("Texture not found under resources root: %s", relative)
        return None

    debug("load shader texture: %s", path)

    return load_blender_image(path)


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


def _matrix_rows_from_text(raw: str) -> list[list[float]]:
    """The three components of each row of a ``float4x4`` value.

    The fourth column is not kept: a row socket is a plain vector.
    """

    values = _parse_floats(raw)

    return [
        (values[start: start + 4] + [0.0, 0.0, 0.0])[:3]
        for start in range(0, 16, 4)
    ]


def _socket_value_for_text(socket_id: str, raw: str):
    """What a socket of type ``socket_id`` is set to for a paramstring value.

    ``None`` when the text leaves the socket as it is. A colour socket cannot
    hold a negative component, so the value is the one it ends up with.
    """

    values = _parse_floats(raw)

    if "Float" in socket_id:

        return values[0] if values else None

    if "Int" in socket_id:

        return int(values[0]) if values and isfinite(values[0]) else None

    if "Vector" in socket_id:

        return (values + [0.0, 0.0, 0.0])[:3]

    if "Color" in socket_id:

        if len(values) >= 4:
            return [max(value, 0.0) for value in values[:4]]

        if len(values) == 3:
            return [*(max(value, 0.0) for value in values), 1.0]

        if len(values) == 1:
            return [max(values[0], 0.0)] * 3 + [1.0]

    return None


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


@dataclass(frozen=True)
class _SocketSpec:
    """One input socket a group needs, with the PARAMCOMMENT it comes from."""

    name: str
    socket_type: str
    description: str
    default: object
    param: ShaderParamComment


def _socket_specs(param: ShaderParamComment) -> list[_SocketSpec]:
    """Sockets for one parameter: none, one, or four rows for a matrix."""

    if param.value_type == "float4x4":

        return [
            _SocketSpec(
                name=f"{param.name}_r{row_index}",
                socket_type="NodeSocketVector",
                description=param.description,
                default=[0.0, 0.0, 0.0],
                param=param,
            )
            for row_index in range(4)
        ]

    socket_type = _socket_type_for_param(param)

    if socket_type is None:

        return []

    return [
        _SocketSpec(
            name=param.name,
            socket_type=socket_type,
            description=param.description,
            default=_default_for_socket(param, socket_type),
            param=param,
        )
    ]


def _effect_socket_specs(effect: ShaderEffect) -> list[_SocketSpec]:

    return [spec for param in effect.params for spec in _socket_specs(param)]


def _input_sockets(node_tree: NodeTree) -> list:

    return [
        item for item in node_tree.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    ]


def _create_socket(node_tree: NodeTree, spec: _SocketSpec):

    socket = node_tree.interface.new_socket(
        name=spec.name,
        in_out="INPUT",
        socket_type=spec.socket_type,
    )
    socket.description = spec.description

    if spec.default is not None:

        socket.default_value = spec.default

    return socket


def _group_nodes_using(node_tree: NodeTree) -> list[Node]:
    """Every group node in the file that instances ``node_tree``."""

    trees: list[NodeTree] = [
        material.node_tree for material in bpy.data.materials
        if material.node_tree is not None
    ]
    trees.extend(
        world.node_tree for world in bpy.data.worlds
        if world.node_tree is not None
    )
    trees.extend(
        light.node_tree for light in bpy.data.lights
        if light.node_tree is not None
    )
    trees.extend(bpy.data.node_groups)

    return [
        node
        for tree in trees
        for node in tree.nodes
        if node.bl_idname == "ShaderNodeGroup" and node.node_tree == node_tree
    ]


def _apply_defaults_to_group_nodes(
        node_tree: NodeTree,
        added: list[tuple[str, _SocketSpec]]) -> None:
    """Give the new sockets of existing group nodes the ShaderLib default.

    A group node takes its new socket the moment the interface item exists,
    which is before the item's default is set, so it starts at the plain
    socket default (0).
    """

    if not added or not node_tree.users:

        return

    for node in _group_nodes_using(node_tree):

        by_identifier = {socket.identifier: socket for socket in node.inputs}

        for identifier, spec in added:

            socket = by_identifier.get(identifier)

            if socket is not None and spec.default is not None:

                socket.default_value = spec.default


def _sync_interface(
        node_tree: NodeTree,
        specs: list[_SocketSpec],
        previous: list[ShaderParamComment]) -> None:
    """Bring the group inputs to ``specs`` without touching the kept ones.

    A socket that still exists with the same name and type keeps its
    identifier, so every group node keeps its value and its links. Only
    added sockets are created, and sockets that are gone are removed.
    """

    interface = node_tree.interface
    previous_by_name = {param.name: param for param in previous}
    unclaimed: dict[str, list] = {}
    stale: list = []

    for item in interface.items_tree:

        if item.item_type == "SOCKET" and item.in_out == "INPUT":

            unclaimed.setdefault(item.name, []).append(item)

        else:

            stale.append(item)

    plan: list = []

    for spec in specs:

        old = previous_by_name.get(spec.param.name)
        same_type = old is None or old.value_type == spec.param.value_type
        match = None

        if same_type:

            for candidate in unclaimed.get(spec.name, []):

                if candidate.socket_type == spec.socket_type:

                    match = candidate
                    break

        if match is not None:

            unclaimed[spec.name].remove(match)

        plan.append(match)

    removed = stale + [i for items in unclaimed.values() for i in items]

    for item in removed:

        interface.remove(item)

    sockets: list = []
    added: list[tuple[str, _SocketSpec]] = []

    for spec, match in zip(specs, plan):

        if match is None:

            socket = _create_socket(node_tree, spec)
            added.append((socket.identifier, spec))

        else:

            socket = match
            old = previous_by_name.get(spec.param.name)

            if socket.description != spec.description:

                socket.description = spec.description

            # Only the default of nodes made from now on changes; existing
            # nodes keep their own values.
            if old != spec.param and spec.default is not None:

                socket.default_value = spec.default

        sockets.append(socket)

    # Each socket is moved up from further down, which keeps the position.
    for position, socket in enumerate(sockets):

        if interface.items_tree[position].identifier != socket.identifier:

            interface.move(socket, position)

    _apply_defaults_to_group_nodes(node_tree, added)

    debug(
        "node group %s: kept %d, added %d, removed %d sockets",
        node_tree.name,
        len(sockets) - len(added),
        len(added),
        len(removed),
    )


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


def _is_up_to_date(
        node_tree: NodeTree,
        library: ShaderLibrary,
        effect: ShaderEffect,
        specs: list[_SocketSpec]) -> bool:
    """Whether the group already is what the ShaderLib describes."""

    if node_tree.get(_PARAMS_KEY) is None:

        return False

    if (node_tree.get("soulworker_library") != library.stem
            or node_tree.get("soulworker_effect") != effect.name):

        return False

    if _load_param_metadata(node_tree) != effect.params:

        return False

    wanted = [(spec.name, spec.socket_type) for spec in specs]
    present = [
        (item.name, item.socket_type) for item in _input_sockets(node_tree)
    ]

    return wanted == present


def ensure_effect_node_group(
        library: ShaderLibrary,
        effect: ShaderEffect) -> NodeTree:
    """Create a parameter-only shader node group for an EFFECT, or update it.

    A group that already matches the ShaderLib is left alone. When the
    parameters changed, the sockets that remain keep their identity, so group
    nodes in materials keep their values and links.
    """

    name = node_group_name(library.stem, effect.name)
    node_tree = bpy.data.node_groups.get(name)
    specs = _effect_socket_specs(effect)

    if node_tree is None:

        node_tree = bpy.data.node_groups.new(name, "ShaderNodeTree")

    elif _is_up_to_date(node_tree, library, effect, specs):

        return node_tree

    _sync_interface(node_tree, specs, _load_param_metadata(node_tree))

    nodes = node_tree.nodes

    if not any(node.bl_idname == "NodeGroupInput" for node in nodes):

        nodes.new("NodeGroupInput")

    if not any(node.bl_idname == "NodeGroupOutput" for node in nodes):

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
    resources_root: Path | str | None = None,
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
    tex_node.image = _load_resource_image(relative, resources_root)

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
    resources_root: Path | str | None = None,
) -> None:

    if param is not None and param.value_type in _TEXTURE_TYPES:

        _set_texture_on_material(
            material_tree, node, param, raw, resources_root)
        return

    socket = node.inputs.get(input_name)

    if socket is None:

        return

    value = _socket_value_for_text(socket.bl_idname, raw)

    if value is not None:

        socket.default_value = value


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
        shader: ShaderTag,
        resources_root: Path | str | None = None) -> Node | None:
    """Add the EFFECT node group to a material and fill PARAMCOMMENT values.

    ``resources_root`` locates textures named in the paramstring; without it
    the N-panel's ``Unpacked Resources`` setting is used.
    """

    node_tree = material.node_tree

    if node_tree is None:

        error("Material %s has no node tree", material.name)
        return None

    group_tree = find_effect_node_group(shader.library, shader.effect)

    if group_tree is None:

        _report_missing_effect(shader.library, shader.effect)
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

            for row_index, row in enumerate(_matrix_rows_from_text(raw)):

                socket = group_node.inputs.get(f"{name}_r{row_index}")

                if socket is not None:

                    socket.default_value = row

            continue

        _set_input_value(
            group_node, node_tree, name, raw, param, resources_root)

    return group_node


def _components_from_socket(socket, count: int) -> list[float]:

    raw = getattr(socket, "default_value", 0.0)

    try:

        values = [float(part) for part in raw]

    except TypeError:

        values = [float(raw)]

    return (values + [0.0] * count)[:count]


def _texture_image(
        material_tree: NodeTree,
        group_node: Node,
        param: ShaderParamComment) -> tuple[bool, Image | None]:
    """Whether a texture node feeds the parameter, and the image it holds."""

    found = False
    socket = group_node.inputs.get(param.name)

    if socket is not None:

        for link in socket.links:

            found = True
            image = getattr(link.from_node, "image", None)

            if image is not None and image.filepath:

                return found, image

    tex_node = material_tree.nodes.get(param.name)

    if tex_node is not None:

        found = True
        image = getattr(tex_node, "image", None)

        if image is not None and image.filepath:

            return found, image

    return found, None


def _texture_value_from_nodes(
        material_tree: NodeTree,
        group_node: Node,
        param: ShaderParamComment,
        resources_root: Path | None) -> str:

    _, image = _texture_image(material_tree, group_node, param)

    if image is not None:

        return game_relative_texture_path(image.filepath, resources_root)

    return param.default


def _param_value_from_nodes(
        material_tree: NodeTree,
        group_node: Node,
        param: ShaderParamComment,
        resources_root: Path | None) -> str:

    if param.value_type in _TEXTURE_TYPES:

        return _texture_value_from_nodes(
            material_tree,
            group_node,
            param,
            resources_root,
        )

    if param.value_type == "float4x4":

        values: list[float] = []

        for row_index in range(4):

            socket = group_node.inputs.get(f"{param.name}_r{row_index}")

            if socket is None:

                values.extend([0.0, 0.0, 0.0, 1.0 if row_index == 3 else 0.0])
                continue

            values.extend(_components_from_socket(socket, 3))
            values.append(1.0 if row_index == 3 else 0.0)

        return ",".join(format_param_float(value) for value in values)

    socket = group_node.inputs.get(param.name)

    if socket is None:

        return param.default

    match param.value_type:

        case "float":
            return format_param_float(_components_from_socket(socket, 1)[0])

        case "int":
            return str(int(_components_from_socket(socket, 1)[0]))

        case "float2":
            return ",".join(
                format_param_float(value)
                for value in _components_from_socket(socket, 2)
            )

        case "float3":
            return ",".join(
                format_param_float(value)
                for value in _components_from_socket(socket, 3)
            )

        case "float4":
            return ",".join(
                format_param_float(value)
                for value in _components_from_socket(socket, 4)
            )

    return param.default


def _float32(value: float) -> float:

    try:

        return unpack("f", pack("f", value))[0]

    except OverflowError:

        return copysign(inf, value)


def _socket_holds_value(socket, expected) -> bool:
    """Whether a socket has the value, as far as a float32 socket can tell."""

    if isinstance(expected, (list, tuple)):

        wanted = [float(component) for component in expected]

    else:

        wanted = [float(expected)]

    actual = _components_from_socket(socket, len(wanted))

    return all(
        _float32(have) == _float32(want) or (have != have and want != want)
        for have, want in zip(actual, wanted)
    )


def _resource_key(path: str) -> str:

    return path.replace("\\", "/").strip().lstrip("/").lower()


def _image_is_resource(
        image: Image,
        text: str,
        resources_root: Path | None) -> bool:
    """Whether the image is the file a paramstring value names."""

    if _resource_key(text) == _resource_key(
            game_relative_texture_path(image.filepath, resources_root)):

        return True

    wanted = (
        resolve_resource_path(resources_root, text)
        if resources_root is not None and text.strip() else None
    )

    if wanted is None:

        return False

    try:

        return wanted.samefile(bpy.path.abspath(image.filepath))

    except OSError:

        return False


def _texture_holds_text(
        material_tree: NodeTree,
        group_node: Node,
        param: ShaderParamComment,
        text: str,
        resources_root: Path | None) -> bool:
    """Whether the texture nodes of a parameter are what ``text`` names.

    A texture node without an image counts as holding any text: the file
    could not be loaded when the material was imported.
    """

    found, image = _texture_image(material_tree, group_node, param)

    if image is not None:

        return _image_is_resource(image, text, resources_root)

    return found or _resource_key(text) == _resource_key(param.default)


def _inputs_hold_text(
        material_tree: NodeTree,
        group_node: Node,
        param: ShaderParamComment,
        text: str,
        resources_root: Path | None) -> bool:
    """Whether the sockets of a parameter still have what ``text`` gives them.

    That is the value the importer sets from the same text, which can differ
    from the text itself: a ``float3`` colour read from four numbers keeps
    its alpha in the socket only.
    """

    if param.value_type in _TEXTURE_TYPES:

        return _texture_holds_text(
            material_tree, group_node, param, text, resources_root)

    if param.value_type == "float4x4":

        for row_index, row in enumerate(_matrix_rows_from_text(text)):

            socket = group_node.inputs.get(f"{param.name}_r{row_index}")

            if socket is not None and not _socket_holds_value(socket, row):

                return False

        return True

    socket = group_node.inputs.get(param.name)

    if socket is None:

        return True

    expected = _socket_value_for_text(socket.bl_idname, text)

    if expected is None:

        expected = _default_for_socket(param, socket.bl_idname)

    return expected is None or _socket_holds_value(socket, expected)


def _inputs_hold_default(
        material_tree: NodeTree,
        group_node: Node,
        param: ShaderParamComment,
        resources_root: Path | None) -> bool:
    """Whether the sockets of a parameter still have the ShaderLib default."""

    if param.value_type in _TEXTURE_TYPES:

        return _texture_holds_text(
            material_tree, group_node, param, param.default, resources_root)

    for spec in _socket_specs(param):

        socket = group_node.inputs.get(spec.name)

        if (socket is not None and spec.default is not None
                and not _socket_holds_value(socket, spec.default)):

            return False

    return True


def _entry_text_from_nodes(
        material_tree: NodeTree,
        group_node: Node,
        param: ShaderParamComment,
        source_text: str | None,
        resources_root: Path | None) -> str | None:
    """Text for a parameter of a material that came with a paramstring.

    ``None`` when the sockets still hold what the import made of
    ``source_text`` (or the ShaderLib default, for a parameter the source did
    not have): the source then speaks for the parameter, with its own text.
    """

    if source_text is None:

        unchanged = _inputs_hold_default(
            material_tree, group_node, param, resources_root)

    else:

        unchanged = _inputs_hold_text(
            material_tree, group_node, param, source_text, resources_root)

    if unchanged:

        return None

    return _param_value_from_nodes(
        material_tree, group_node, param, resources_root)


def _imported_paramstring(
        material: Material,
        library: str,
        effect: str) -> ShaderParamString | None:
    """The paramstring the material was imported with, if it is for this effect."""

    raw = material.get("soulworker_shader_paramstring")

    if raw is None or material.get("soulworker_shader_effect") != effect:

        return None

    imported_library = str(material.get("soulworker_shader_library", ""))

    if imported_library.lower() != library.lower():

        return None

    return ShaderParamString(str(raw))


def collect_shader_from_material(
        material: Material,
        resources_root: Path | None = None) -> tuple[str, str, str] | None:
    """Return ``(library_stem, effect, paramstring)`` from an EFFECT node group.

    A material made in Blender gets every PARAMCOMMENT parameter of the
    ShaderLib metadata stored on the node group, in that order. A material
    that was imported keeps the paramstring it came with: the same entries,
    in the same order and with the same text. Only a parameter whose socket
    the user changed takes the socket's value, and a parameter the source
    lacks is added, after the others, only when its socket is no longer the
    ShaderLib default.
    """

    node_tree = material.node_tree

    if node_tree is None:

        return None

    for node in node_tree.nodes:

        if node.bl_idname != "ShaderNodeGroup":

            continue

        group_tree = node.node_tree

        if group_tree is None:

            continue

        effect = group_tree.get("soulworker_effect")
        library = group_tree.get("soulworker_library")

        if not effect or not library:

            continue

        params = _load_param_metadata(group_tree)

        if not params:

            continue

        root = resources_root

        if root is None and material.get("soulworker_resources_root"):

            root = Path(str(material["soulworker_resources_root"]))

        imported = _imported_paramstring(material, str(library), str(effect))

        if imported is not None:

            paramstring = paramstring_in_source_order(
                imported,
                params,
                lambda param, text: _entry_text_from_nodes(
                    node_tree, node, param, text, root),
            )

        else:

            values = {
                param.name: _param_value_from_nodes(
                    node_tree,
                    node,
                    param,
                    root,
                )
                for param in params
            }
            paramstring = paramstring_from_params(params, values)

        return str(library), str(effect), paramstring

    return None
