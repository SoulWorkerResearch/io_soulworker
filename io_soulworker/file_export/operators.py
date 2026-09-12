from logging import debug, error
from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy.types import Context, Operator
from bpy_extras.io_utils import ExportHelper

from io_soulworker.file_export.model_exporter import write_model_file
from io_soulworker.file_export.resources_xml import (
    model_data_dir,
    resolve_export_path,
)
from io_soulworker.file_export.vmesh_exporter import write_vmesh_file
from io_soulworker.file_import.runner import in_blender


def _active_mesh_object(context: Context):

    obj = context.view_layer.objects.active

    if obj is not None and obj.type == "MESH":

        return obj

    for selected in context.selected_objects:

        if selected.type == "MESH":

            return selected

    return None


def _armature_of(mesh_obj):
    """Return the armature object linked to this mesh via an Armature modifier."""

    if mesh_obj is None:

        return None

    for modifier in mesh_obj.modifiers:

        if modifier.type == "ARMATURE" and modifier.object is not None:

            return modifier.object

    if mesh_obj.parent is not None and mesh_obj.parent.type == "ARMATURE":

        return mesh_obj.parent

    return None


def _resources_root(context: Context) -> Path | None:

    raw = getattr(context.scene, "soulworker_unpack_resources", "") or ""
    raw = raw.strip()

    if not raw:

        return None

    root = Path(bpy.path.abspath(raw)).resolve()

    if not root.is_dir():

        return None

    return root


def _export_path(filepath: str, obj, suffix: str) -> Path:

    return resolve_export_path(
        Path(bpy.path.abspath(filepath)),
        obj.name,
        suffix,
    )


class IO_SOULWORKER_OT_export_vmesh(Operator, ExportHelper):
    """Export the active mesh as a static SoulWorker .vmesh."""

    bl_idname = "io_soulworker.export_vmesh"
    bl_label = "Export SoulWorker .vmesh"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".vmesh"

    if in_blender():

        filter_glob: StringProperty(
            default="*.vmesh",
            options={"HIDDEN"},
        )  # type: ignore

    else:

        filter_glob: str

    def invoke(self, context: Context, event):

        obj = _active_mesh_object(context)

        if obj is None:

            self.report({"ERROR"}, "Select a mesh object to export")
            return {"CANCELLED"}

        if not self.filepath:

            self.filepath = bpy.path.ensure_ext(obj.name, self.filename_ext)

        return ExportHelper.invoke(self, context, event)

    def execute(self, context: Context):

        obj = _active_mesh_object(context)

        if obj is None:

            self.report({"ERROR"}, "Select a mesh object to export")
            return {"CANCELLED"}

        path = _export_path(self.filepath, obj, self.filename_ext)

        try:

            write_vmesh_file(path, obj, _resources_root(context))

        except Exception as exc:

            error("Failed to export .vmesh %s: %s", path, exc)
            self.report({"ERROR"}, f"Export failed: {exc}")
            return {"CANCELLED"}

        debug("exported .vmesh: %s", path)
        self.report(
            {"INFO"},
            f"Exported {path.name} and {model_data_dir(path).name}",
        )
        return {"FINISHED"}


class IO_SOULWORKER_OT_export_model(Operator, ExportHelper):
    """Export the active mesh (+ armature) as a dynamic SoulWorker .model."""

    bl_idname = "io_soulworker.export_model"
    bl_label = "Export SoulWorker .model"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".model"

    if in_blender():

        filter_glob: StringProperty(
            default="*.model",
            options={"HIDDEN"},
        )  # type: ignore

    else:

        filter_glob: str

    def invoke(self, context: Context, event):

        obj = _active_mesh_object(context)
        name = obj.name if obj is not None else "untitled"

        if not self.filepath:

            self.filepath = bpy.path.ensure_ext(name, self.filename_ext)

        return ExportHelper.invoke(self, context, event)

    def execute(self, context: Context):

        obj = _active_mesh_object(context)

        if obj is None:

            self.report({"ERROR"}, "Select a mesh object to export")
            return {"CANCELLED"}

        path = _export_path(self.filepath, obj, self.filename_ext)

        armature_obj = _armature_of(obj)

        try:

            write_model_file(path, obj, armature_obj, _resources_root(context))

        except Exception as exc:

            error("Failed to export .model %s: %s", path, exc)
            self.report({"ERROR"}, f"Export failed: {exc}")
            return {"CANCELLED"}

        debug("exported .model: %s", path)
        data_name = model_data_dir(path).name

        if armature_obj is None:

            self.report(
                {"WARNING"},
                f"Exported {path.name} and {data_name} without skeleton",
            )

        else:

            self.report({"INFO"}, f"Exported {path.name} and {data_name}")

        return {"FINISHED"}
