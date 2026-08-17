from __future__ import annotations

import bpy

from bpy.types import Collection, Context, LayerCollection


def get_layer_collection(
    layer_collection: LayerCollection,
    collection: Collection,
) -> LayerCollection | None:

    if layer_collection.collection == collection:
        return layer_collection

    for layer in layer_collection.children:
        found = get_layer_collection(layer, collection)

        if found is not None:
            return found

    return None


def set_active_collection(context: Context, collection: Collection) -> None:

    view_layer = context.view_layer
    layer_collection = get_layer_collection(
        view_layer.layer_collection,
        collection,
    )

    if layer_collection is not None:
        view_layer.active_layer_collection = layer_collection


def find_or_create_child_collection(
    parent: Collection,
    name: str,
) -> Collection:

    for child in parent.children:
        if child.name == name:
            return child

    new_collection = bpy.data.collections.new(name)
    parent.children.link(new_collection)

    return new_collection


def ensure_collection_hierarchy(
    context: Context,
    segment_names: list[str],
) -> Collection:

    current = context.scene.collection

    for name in segment_names:
        current = find_or_create_child_collection(current, name)

    return current


def collection_segments_under_resources(
    resources_root_raw: str,
    file_path,
) -> list[str] | None:
    """Build ``project/…`` collection segments for a path under the resources root."""

    from pathlib import Path

    root_raw = (resources_root_raw or "").strip()

    if not root_raw:
        return None

    root = Path(bpy.path.abspath(root_raw)).resolve()
    target_parent = Path(bpy.path.abspath(str(file_path))).resolve().parent

    try:
        relative = target_parent.relative_to(root)
    except ValueError:
        return None

    if relative == Path("."):
        return ["project"]

    return ["project", *relative.parts]


def leaf_collection_color_tag(file_path) -> str:

    from pathlib import Path

    ext = Path(file_path).suffix.lower()

    if ext == ".model":
        return "COLOR_02"

    if ext == ".vmesh":
        return "COLOR_03"

    if ext == ".vscene":
        return "COLOR_04"

    return "NONE"
