import bpy

from logging import debug, error
from pathlib import Path

from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Context, Operator, Panel, Scene

from io_soulworker.file_export.operators import (
    IO_SOULWORKER_OT_export_model,
    IO_SOULWORKER_OT_export_vmesh,
)
from io_soulworker.file_import.animation.file_reader import AnimationFileReader
from io_soulworker.file_import.collections import (
    collection_segments_under_resources,
    ensure_collection_hierarchy,
    leaf_collection_color_tag,
    set_active_collection,
)
from io_soulworker.file_import.model.file_reader import ModelFileReader
from io_soulworker.file_import.runner import in_blender
from io_soulworker.file_import.scene.importer import SceneImporter
from io_soulworker.file_import.shaders.node_groups import sync_shader_node_groups


def _on_unpack_resources_update(scene: Scene, _context: Context) -> None:

    count = sync_shader_node_groups(scene.soulworker_unpack_resources)

    debug("ShaderLib sync finished: %d effects", count)


@persistent
def _sync_shader_libs_on_load(_dummy) -> None:

    import bpy

    for scene in bpy.data.scenes:

        root = getattr(scene, "soulworker_unpack_resources", "") or ""

        if root.strip():

            sync_shader_node_groups(root)


def _resources_root(context: Context) -> Path | None:

    raw = (context.scene.soulworker_unpack_resources or "").strip()

    if not raw:
        return None

    root = Path(bpy.path.abspath(raw)).resolve()

    if not root.is_dir():
        return None

    return root


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

        segments = collection_segments_under_resources(
            context.scene.soulworker_unpack_resources,
            path,
        )

        collection = None

        if segments is not None:

            collection = ensure_collection_hierarchy(context, segments)
            collection.color_tag = leaf_collection_color_tag(path)

            set_active_collection(context, collection)

        elif (context.scene.soulworker_unpack_resources or "").strip():

            self.report(
                {"WARNING"},
                "The file is not inside the specified resources folder; no collection hierarchy was created",
            )

        ModelFileReader(
            path,
            context,
            7.0,
            collection=collection,
        ).run()

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


class IO_SOULWORKER_OT_open_scene(Operator, ImportHelper):

    bl_idname = "io_soulworker.open_scene"
    bl_label = "Open Scene"
    bl_options = {"REGISTER", "UNDO"}

    if in_blender():

        filter_glob: StringProperty(
            default="*.vscene", options={"HIDDEN"})  # type: ignore

    else:

        filter_glob: str

    def execute(self, context: Context):

        context.scene.render.engine = "BLENDER_EEVEE"

        path = Path(self.filepath)
        ext = path.suffix.lower()

        if not path.is_file() or ext != ".vscene":
            error("not a .vscene file: %s", path)
            self.report({"ERROR"}, "A .vscene file is required")
            return {"CANCELLED"}

        resources = _resources_root(context)

        if resources is None:
            self.report(
                {"ERROR"},
                "Set SoulWorker Resources to the unpacked _datas folder first",
            )
            return {"CANCELLED"}

        try:
            result = SceneImporter(
                path,
                context,
                resources,
                emission_strength=7.0,
            ).run()
        except Exception as exc:
            error("Scene import failed: %s", exc)
            self.report({"ERROR"}, f"Scene import failed: {exc}")
            return {"CANCELLED"}

        placed = len(result.objects)
        missing = len(result.missing_paths)
        total = result.static_mesh_count + result.zone_mesh_count

        if placed == 0 and total == 0:
            self.report({"WARNING"}, "Scene has no static mesh instances")
        elif placed == 0:
            self.report(
                {"ERROR"},
                f"No meshes placed ({missing} missing under Resources)",
            )
            return {"CANCELLED"}
        elif missing:
            self.report(
                {"WARNING"},
                f"Placed {placed}/{total} meshes "
                f"({missing} missing)",
            )
        else:
            self.report(
                {"INFO"},
                f"Placed {placed} static mesh instance(s)",
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
            text="Open Model",
        )
        layout.operator(
            IO_SOULWORKER_OT_open_scene.bl_idname,
            text="Open Scene",
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

    import bpy

    Scene.soulworker_unpack_resources = StringProperty(
        name="Resources",
        description="Root folder of unpacked SoulWorker resources",
        default="",
        subtype="DIR_PATH",
        update=_on_unpack_resources_update,
    )

    if _sync_shader_libs_on_load not in bpy.app.handlers.load_post:

        bpy.app.handlers.load_post.append(_sync_shader_libs_on_load)


def unregister_unpack_resources_props():

    import bpy

    if _sync_shader_libs_on_load in bpy.app.handlers.load_post:

        bpy.app.handlers.load_post.remove(_sync_shader_libs_on_load)

    del Scene.soulworker_unpack_resources
