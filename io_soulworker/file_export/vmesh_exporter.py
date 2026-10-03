from __future__ import annotations

from pathlib import Path

from io_soulworker.chunks.expr_chunk import ExprChunk
from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.subm_chunk import VisSubMeshChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.vis_bin_header import VisBinHeader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_writer_scope import (
    VisChunkWriterScope,
    write_chunk_file_eof,
)
from io_soulworker.file_export.materials_xml import MaterialSidecar
from io_soulworker.file_export.mesh_builder import (
    build_geometry,
    build_material_sidecars,
    mtrs_from_sidecars,
)
from io_soulworker.file_export.resources_xml import write_export_sidecars


class VmeshExportData:
    """Serializable payload for a static .vmesh file."""

    def __init__(
        self,
        mesh: VMshChunk,
        materials: list[MtrsChunk],
        sidecars: list[MaterialSidecar],
        sub_meshes: VisSubMeshChunk,
        export_transform: ExprChunk,
    ) -> None:

        self.mesh = mesh
        self.materials = materials
        self.sidecars = sidecars
        self.sub_meshes = sub_meshes
        self.export_transform = export_transform


def build_vmesh_from_blender_object(
        obj,
        resources_root: Path | None = None) -> VmeshExportData:
    """Build Vision static-mesh chunks from a Blender MESH object."""

    geometry = build_geometry(obj)
    sidecars = build_material_sidecars(obj, resources_root)
    materials = mtrs_from_sidecars(sidecars)

    expr = ExprChunk()
    expr.version = ExprChunk.LOCAL_VERSION
    expr.flag = 1

    return VmeshExportData(
        geometry.mesh,
        materials,
        sidecars,
        geometry.sub_meshes,
        expr,
    )


def _write_mtrs_chunk(writer: BinaryWriter, materials: list[MtrsChunk]) -> None:

    with VisChunkWriterScope(writer, VisChunkId.MTRS) as payload:

        payload.write_uint32(len(materials))

        for material in materials:

            material.write(payload)


def write_vmesh_file(
        path: Path,
        obj,
        resources_root: Path | None = None) -> None:

    data = build_vmesh_from_blender_object(obj, resources_root)
    path.parent.mkdir(parents=True, exist_ok=True)

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

    write_export_sidecars(
        path,
        data.sidecars,
        resources_root=resources_root,
    )
