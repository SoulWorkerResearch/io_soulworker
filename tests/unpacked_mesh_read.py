from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from logging import INFO, NOTSET, disable, error
from pathlib import Path
from time import perf_counter

from io_soulworker.file_import.model.chunk_reader import ModelChunkReader


PROGRESS_EVERY = 250


@dataclass(frozen=True)
class MeshReadFailure:

    path: Path
    message: str


class _SilentModelReader(ModelChunkReader):
    """Parse every known chunk without the per-chunk ``info`` spam."""

    def on_chunk_start(self, scope, reader) -> None:

        if scope.depth < 0:
            return

        super().on_chunk_start(scope, reader)


def parse_mesh(path: Path) -> None:

    _SilentModelReader(path).run()


def import_mesh(path: Path) -> None:

    from io_soulworker.file_import.runner import in_blender

    if not in_blender():
        raise RuntimeError("import_mesh requires a real Blender bpy module")

    import bpy

    from io_soulworker.file_import.model.file_reader import ModelFileReader

    reader = ModelFileReader(
        path,
        bpy.context,
        7.0,
        reuse_mesh=False,
    )

    try:
        reader.run()
    finally:
        _purge_imported_data()


def _purge_imported_data() -> None:

    import bpy

    from io_soulworker.file_import.model.file_reader import clear_mesh_cache

    clear_mesh_cache()

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)

    for armature in list(bpy.data.armatures):
        bpy.data.armatures.remove(armature)

    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)

    for image in list(bpy.data.images):
        bpy.data.images.remove(image)

    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def read_mesh(path: Path, *, blender_import: bool) -> None:

    if blender_import:
        import_mesh(path)
        return

    parse_mesh(path)


def read_all_meshes(
    files: list[Path],
    *,
    blender_import: bool = False,
    on_progress: Callable[[int, int, Path], None] | None = None,
) -> list[MeshReadFailure]:

    failures: list[MeshReadFailure] = []
    total = len(files)
    disable(INFO)

    try:
        for index, path in enumerate(files, 1):

            if on_progress is not None and (
                    index == 1 or index % PROGRESS_EVERY == 0 or index == total):
                on_progress(index, total, path)

            try:
                read_mesh(path, blender_import=blender_import)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                error("%s -> %s", path, message)
                failures.append(
                    MeshReadFailure(
                        path, f"{message}\n{traceback.format_exc()}")
                )
    finally:
        disable(NOTSET)

    return failures


def write_failure_report(
        failures: list[MeshReadFailure],
        report: Path,
        root: Path) -> None:

    lines = []

    for item in failures:
        try:
            relative = item.path.relative_to(root)
        except ValueError:
            relative = item.path

        lines.append(f"===== {relative} =====\n{item.message.rstrip()}\n")

    report.write_text("\n".join(lines), encoding="utf-8")


def format_failure_summary(
        failures: list[MeshReadFailure],
        root: Path,
        *,
        limit: int = 40) -> str:

    rows = []

    for item in failures[:limit]:
        try:
            relative = item.path.relative_to(root)
        except ValueError:
            relative = item.path

        first_line = item.message.strip().splitlines()[0]
        rows.append(f"  {relative}: {first_line}")

    extra = len(failures) - limit

    if extra > 0:
        rows.append(f"  ... and {extra} more")

    return "\n".join(rows)


def log_progress(index: int, total: int, path: Path, started: float) -> None:

    elapsed = perf_counter() - started
    print(f"mesh read {index}/{total} ({elapsed:.1f}s) {path}", flush=True)
