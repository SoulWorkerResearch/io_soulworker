from __future__ import annotations

from pathlib import Path


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
