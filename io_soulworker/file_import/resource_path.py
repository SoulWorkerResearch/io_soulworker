from __future__ import annotations

from logging import error
from pathlib import Path

import bpy
from bpy.types import Image


def normalize_resource_relative(relative: str) -> Path:
    """Normalize Vision backslash paths to a relative ``Path``."""

    cleaned = relative.replace("\\", "/").lstrip("/")
    return Path(cleaned)


BUILTIN_TEXTURES = {"plainwhite.dds"}
"""Textures Vision provides from its own resources; never on disk."""


def is_builtin_texture(relative: str) -> bool:
    """``\\PlainWhite.DDS`` and friends: the engine's internal fallbacks."""

    name = relative.replace("\\", "/").rsplit("/", 1)[-1]

    return name.lower() in BUILTIN_TEXTURES


def _walk_case_insensitive(start: Path, parts: tuple[str, ...]) -> Path | None:
    """Follow ``parts`` below ``start`` matching each name without case.

    ``.`` and ``..`` are honoured so mesh-relative references such as
    ``..\\..\\Textures\\x.dds`` work even when the archive casing differs
    from the unpacked tree (``f031`` vs ``F031``).
    """

    current = start

    for part in parts:
        if part in ("", "."):
            continue

        if part == "..":
            current = current.parent
            continue

        if not current.is_dir():
            return None

        exact = current / part

        if exact.exists():
            current = exact
            continue

        by_lower = {child.name.lower(): child for child in current.iterdir()}
        hit = by_lower.get(part.lower())

        if hit is None:
            return None

        current = hit

    if current.is_file():
        return current.resolve()

    return None


def resolve_resource_path(
        resources_root: Path | str,
        relative: str) -> Path | None:
    """Resolve a game-relative (or absolute) path under ``resources_root``.

    Tries an exact join first, then a case-insensitive walk (Linux vs Windows
    archives often disagree on casing, e.g. ``UI_sphere_01`` vs ``UI_Sphere_01``).
    An absolute POSIX path is tried as-is before falling back to treating it
    as root-relative, so export sidecars and Vision's ``\\Textures\\x.dds``
    style both resolve.
    """

    root = Path(resources_root)
    cleaned = relative.replace("\\", "/")
    candidate = Path(cleaned)

    if candidate.is_absolute():
        if candidate.is_file():
            return candidate.resolve()

        found = _walk_case_insensitive(
            Path(candidate.anchor), candidate.parts[1:])

        if found is not None:
            return found

    rel = normalize_resource_relative(relative)

    if not rel.parts:
        return None

    exact = root / rel

    if exact.is_file():
        return exact.resolve()

    return _walk_case_insensitive(root, rel.parts)


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
