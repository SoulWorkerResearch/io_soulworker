import bpy

from logging import debug, error
from pathlib import Path

from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Collection, Context, LayerCollection, Operator, Panel, Scene

from io_soulworker.file_export.operators import (
    IO_SOULWORKER_OT_export_model,
    IO_SOULWORKER_OT_export_vmesh,
)
from io_soulworker.file_import.animation.file_reader import AnimationFileReader
from io_soulworker.file_import.model.file_reader import ModelFileReader
from io_soulworker.file_import.runner import in_blender


def _get_layer_collection(
    layer_collection: LayerCollection,
    collection: Collection,
) -> LayerCollection | None:

    if layer_collection.collection == collection:

        return layer_collection

    for layer in layer_collection.children:

        found = _get_layer_collection(layer, collection)

        if found is not None:

            return found

    return None


def _set_active_collection(context: Context, collection: Collection) -> None:

    view_layer = context.view_layer
    layer_collection = _get_layer_collection(
        view_layer.layer_collection,
        collection,
    )

    if layer_collection is not None:

        view_layer.active_layer_collection = layer_collection


def _find_or_create_child_collection(
    parent: Collection,
    name: str,
) -> Collection:

    for child in parent.children:

        if child.name == name:

            return child

    new_collection = bpy.data.collections.new(name)
    parent.children.link(new_collection)

    return new_collection


def _ensure_collection_hierarchy(
    context: Context,
    segment_names: list[str],
) -> Collection:

    current = context.scene.collection

    for name in segment_names:

        current = _find_or_create_child_collection(current, name)

    return current


def _collection_segments_for_model(
    resources_root_raw: str,
    model_path: Path,
) -> list[str] | None:

    root_raw = (resources_root_raw or "").strip()

    if not root_raw:

        return None

    root = Path(bpy.path.abspath(root_raw)).resolve()
    model_parent = Path(bpy.path.abspath(str(model_path))).resolve().parent

    try:

        relative = model_parent.relative_to(root)

    except ValueError:

        return None

    if relative == Path("."):

        return ["project"]

    return ["project", *relative.parts]


def _leaf_collection_color_tag(model_path: Path) -> str:

    ext = model_path.suffix.lower()

    if ext == ".model":

        return "COLOR_02"

    if ext == ".vmesh":

        return "COLOR_03"

    return "NONE"


class IO_SOULWORKER_OT_open_resource(Operator, ImportHelper):

    bl_idname = "io_soulworker.open_resource"
    bl_label = "Open Resource"
    bl_options = {"REGISTER", "UNDO"}

    if in_blender():

        filter_glob: StringProperty(
            default="*.model;*.vmesh", options={"HIDDEN"})  # type: ignore

    else:

        filter_glob: str

    def execute(self, context: Context):

        context.scene.render.engine = "BLENDER_EEVEE"

        path = Path(self.filepath)

        ext = path.suffix.lower()
        if not path.is_file() or ext not in {".model", ".vmesh"}:

            error("not a .model/.vmesh file: %s", path)
            self.report({"ERROR"}, "A .model or .vmesh file is required")
            return {"CANCELLED"}

        segments = _collection_segments_for_model(
            context.scene.soulworker_unpack_resources,
            path,
        )

        if segments is not None:

            leaf = _ensure_collection_hierarchy(context, segments)
            leaf.color_tag = _leaf_collection_color_tag(path)

            _set_active_collection(context, leaf)

        elif (context.scene.soulworker_unpack_resources or "").strip():

            self.report(
                {"WARNING"},
                "The file is not inside the specified resources folder; no collection hierarchy was created",
            )

        ModelFileReader(path, context, 7.0).run()

        # If an animation with the same stem exists next to the model - import it too.
        anim_path = path.with_suffix(".anim")
        if anim_path.is_file():
            debug("import animation: %s", anim_path)
            try:
                AnimationFileReader(anim_path, context).run()
            except Exception as exc:
                error("Failed to import animation %s: %s", anim_path, exc)
                self.report(
                    {"WARNING"},
                    f"Failed to import animation: {anim_path.name}",
                )

        return {"FINISHED"}


class IO_SOULWORKER_PT_unpack_resources(Panel):
    """Sidebar panel for unpacked game assets root path."""

    bl_idname = "IO_SOULWORKER_PT_unpack_resources"
    bl_label = "Import"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SoulWorker"

    def draw(self, context):

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(context.scene, "soulworker_unpack_resources")

        layout.operator(
            IO_SOULWORKER_OT_open_resource.bl_idname,
            text="Open",
        )


class IO_SOULWORKER_PT_export(Panel):
    """Sidebar panel for SoulWorker model export."""

    bl_idname = "IO_SOULWORKER_PT_export"
    bl_label = "Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SoulWorker"

    def draw(self, context):

        layout = self.layout
        layout.operator(
            IO_SOULWORKER_OT_export_vmesh.bl_idname,
            text="Static Mesh (.vmesh)",
        )
        layout.operator(
            IO_SOULWORKER_OT_export_model.bl_idname,
            text="Dynamic Mesh (.model)",
        )


def register_unpack_resources_props():

    Scene.soulworker_unpack_resources = StringProperty(
        name="Resources",
        description="Root folder of unpacked SoulWorker resources",
        default="",
        subtype="DIR_PATH",
    )


def unregister_unpack_resources_props():

    del Scene.soulworker_unpack_resources
