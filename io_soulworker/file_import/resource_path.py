from __future__ import annotations

from logging import error
from pathlib import Path

import bpy
from bpy.types import Image


def normalize_resource_relative(relative: str) -> Path:
    """Normalize Vision backslash paths to a relative ``Path``."""

    cleaned = relative.replace("\\", "/").lstrip("/")
    return Path(cleaned)


def resolve_resource_path(
        resources_root: Path | str,
        relative: str) -> Path | None:
    """Resolve a game-relative path under ``resources_root``.

    Tries an exact join first, then a case-insensitive walk (Linux vs Windows
    archives often disagree on casing, e.g. ``UI_sphere_01`` vs ``UI_Sphere_01``).
    """

    root = Path(resources_root)
    rel = normalize_resource_relative(relative)

    if not rel.parts:
        return None

    exact = root / rel

    if exact.is_file():
        return exact.resolve()

    current = root

    for part in rel.parts:
        if not current.is_dir():
            return None

        by_lower = {child.name.lower(): child for child in current.iterdir()}
        hit = by_lower.get(part.lower())

        if hit is None:
            return None

        current = hit

    if current.is_file():
        return current.resolve()

    return None


def game_relative_texture_path(
        filepath: str,
        resources_root: Path | str | None = None) -> str:
    """Turn a Blender image path into a Vision backslash resource path."""

    raw = (filepath or "").strip()

    if not raw:

        return ""

    abs_path = Path(bpy.path.abspath(raw))

    try:

        resolved = abs_path.resolve()

    except OSError:

        resolved = abs_path

    if resources_root:

        root = Path(resources_root)

        try:

            root = root.resolve()

        except OSError:

            pass

        try:

            return str(resolved.relative_to(root)).replace("/", "\\")

        except ValueError:

            pass

    cleaned = raw.replace("/", "\\")

    if cleaned.startswith("//"):

        cleaned = cleaned[2:]

    cleaned = cleaned.lstrip("\\")

    return cleaned or resolved.name


def load_blender_image(path: Path | str) -> Image | None:
    """Load an image datablock; return ``None`` if Blender cannot read it."""

    resolved = Path(path).resolve()

    try:
        return bpy.data.images.load(str(resolved), check_existing=True)
    except RuntimeError as exc:
        error("Cannot load texture %s: %s", resolved, exc)
        return None
