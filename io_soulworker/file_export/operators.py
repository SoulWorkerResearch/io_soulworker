from logging import debug, error
from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy.types import Context, Operator
from bpy_extras.io_utils import ExportHelper

from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.vis_bin_header import VisBinHeader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_writer_scope import (
    VisChunkWriterScope,
    write_chunk_file_eof,
)
from io_soulworker.file_export.vmesh_exporter import build_vmesh_from_blender_object
from io_soulworker.file_import.runner import in_blender


def _active_mesh_object(context: Context):

    obj = context.view_layer.objects.active

    if obj is not None and obj.type == "MESH":

        return obj

    for selected in context.selected_objects:

        if selected.type == "MESH":

            return selected

    return None


def _write_mtrs_chunk(writer: BinaryWriter, materials: list[MtrsChunk]) -> None:

    with VisChunkWriterScope(writer, VisChunkId.MTRS) as payload:

        payload.write_uint32(len(materials))

        for material in materials:

            material.write(payload)


def write_vmesh_file(path: Path, obj) -> None:

    data = build_vmesh_from_blender_object(obj)

    with BinaryWriter(path.open("wb")) as writer:

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

        write_chunk_file_eof(writer)


def write_dummy_model_file(path: Path) -> None:
    """Placeholder .model writer (dynamic mesh export not implemented yet)."""

    with BinaryWriter(path.open("wb")) as writer:

        header = VisBinHeader()
        header.cid = VisChunkId.VBIN
        header.version = 65536
        header.write(writer)
        write_chunk_file_eof(writer)


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

        path = Path(bpy.path.abspath(self.filepath))

        if path.suffix.lower() != ".vmesh":

            path = path.with_suffix(".vmesh")

        try:

            write_vmesh_file(path, obj)

        except Exception as exc:

            error("Failed to export .vmesh %s: %s", path, exc)
            self.report({"ERROR"}, f"Export failed: {exc}")
            return {"CANCELLED"}

        debug("exported .vmesh: %s", path)
        self.report({"INFO"}, f"Exported {path.name}")
        return {"FINISHED"}


class IO_SOULWORKER_OT_export_model(Operator, ExportHelper):
    """Dummy export for dynamic SoulWorker .model files."""

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

        path = Path(bpy.path.abspath(self.filepath))

        if path.suffix.lower() != ".model":

            path = path.with_suffix(".model")

        try:

            write_dummy_model_file(path)

        except Exception as exc:

            error("Failed to export dummy .model %s: %s", path, exc)
            self.report({"ERROR"}, f"Export failed: {exc}")
            return {"CANCELLED"}

        self.report(
            {"WARNING"},
            f"Wrote dummy .model (not a full dynamic mesh): {path.name}",
        )
        return {"FINISHED"}
