from __future__ import annotations

from logging import debug
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, indent

from io_soulworker.core.materials_xml.shader_param_string import ShaderParamString
from io_soulworker.file_export.materials_xml import (
    MaterialSidecar,
    materials_xml_path,
    write_materials_xml,
)


_TEXTURE_SUFFIXES = {".dds", ".tga", ".png", ".jpg", ".jpeg", ".bmp"}


def model_data_dir(mesh_path: Path) -> Path:

    return mesh_path.parent / f"{mesh_path.name}_data"


def resources_xml_path(mesh_path: Path) -> Path:

    return model_data_dir(mesh_path) / "resources.xml"


def resolve_export_path(
        filepath: Path,
        object_name: str,
        suffix: str) -> Path:
    """Treat a suffix-less path as a directory and write ``{object}{suffix}`` inside it."""

    expected = suffix if suffix.startswith(".") else f".{suffix}"
    expected = expected.lower()
    path = Path(filepath)

    if path.suffix.lower() == expected:

        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    if path.suffix == "" or path.is_dir():

        path.mkdir(parents=True, exist_ok=True)
        name = object_name

        if not name.lower().endswith(expected):

            name = f"{name}{expected}"

        return path / name

    path.parent.mkdir(parents=True, exist_ok=True)
    return path.with_suffix(expected)


def write_export_sidecars(
        mesh_path: Path,
        materials: list[MaterialSidecar],
        resources_root: Path | None = None) -> Path:
    """Write ``{mesh.name}_data/materials.xml`` and ``resources.xml``."""

    materials_path = write_materials_xml(
        materials_xml_path(mesh_path),
        materials,
        resources_root=resources_root,
    )
    resources_path = write_resources_xml(
        resources_xml_path(mesh_path),
        mesh_path,
        materials,
        resources_root=resources_root,
    )
    data_dir = materials_path.parent
    debug("export sidecars: %s, %s", materials_path, resources_path)
    return data_dir


def write_resources_xml(
        path: Path,
        mesh_path: Path,
        materials: list[MaterialSidecar],
        resources_root: Path | None = None) -> Path:

    path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, str]] = []

    anim_path = mesh_path.with_suffix(".anim")

    if anim_path.is_file():

        entries.append({
            "Manager": "Animations",
            "Filename": _project_relative(anim_path, resources_root),
            "Size": str(_file_size(anim_path)),
        })

    diffuse_names = _diffuse_texture_names(materials)

    for texture in _texture_paths(materials):

        attrib = {
            "Manager": "Textures",
            "Filename": texture,
            "CustomInt": "1,64" if texture in diffuse_names else "1,0",
            "Size": str(_resource_file_size(texture, resources_root)),
        }
        entries.append(attrib)

    for library in _effect_libraries(materials):

        entries.append({
            "Manager": "EffectLibs",
            "Filename": library,
            "Size": str(_resource_file_size(library, resources_root)),
        })

    materials_relative = _project_relative(
        materials_xml_path(mesh_path),
        resources_root,
    )
    mesh_relative = _project_relative(mesh_path, resources_root)
    mesh_custom = "1,2" if mesh_path.suffix.lower() == ".model" else "1,1"

    mesh_index = len(entries) + 1
    entries.append({
        "Manager": "FILE",
        "Filename": materials_relative,
        "OwnerRes": str(mesh_index),
        "Size": str(_file_size(materials_xml_path(mesh_path))),
    })
    entries.append({
        "Manager": "Static/Dynamic Meshes",
        "Filename": mesh_relative,
        "CustomInt": mesh_custom,
        "Size": str(_file_size(mesh_path)),
    })

    root = Element("root")
    container = Element(
        "Resources",
        {
            "Version": "1",
            "Count": str(len(entries)),
            "PathType": "Project",
        },
    )
    root.append(container)

    for attrib in entries:

        container.append(Element("Resource", attrib))

    indent(root, space="    ")
    tree = ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=False)

    data = path.read_bytes()

    if not data.endswith(b"\n"):

        path.write_bytes(data + b"\n")

    return path


def _backslash(value: str) -> str:

    return value.replace("/", "\\")


def _file_size(path: Path) -> int:

    try:

        return path.stat().st_size

    except OSError:

        return 0


def _project_relative(path: Path, resources_root: Path | None) -> str:

    resolved = path.resolve()

    if resources_root is not None:

        try:

            return _backslash(str(resolved.relative_to(resources_root.resolve())))

        except ValueError:

            pass

    if path.suffix.lower() in {".xml"}:

        return _backslash(str(Path(path.parent.name) / path.name))

    return path.name


def _resource_file_size(relative: str, resources_root: Path | None) -> int:

    if resources_root is None:

        return 0

    candidate = resources_root / relative.replace("\\", "/")

    return _file_size(candidate)


def _normalize_resource_name(raw: str) -> str:

    return _backslash(raw).lstrip("\\")


def _diffuse_texture_names(materials: list[MaterialSidecar]) -> set[str]:

    names: set[str] = set()

    for material in materials:

        cleaned = _normalize_resource_name(material.diffuse)
        suffix = Path(cleaned).suffix.lower()

        if suffix in _TEXTURE_SUFFIXES:

            names.add(cleaned)

    return names


def _add_unique(values: list[str], seen: set[str], raw: str) -> None:

    cleaned = _normalize_resource_name(raw)

    if not cleaned or cleaned in seen:

        return

    seen.add(cleaned)
    values.append(cleaned)


def _texture_paths(materials: list[MaterialSidecar]) -> list[str]:

    seen: set[str] = set()
    result: list[str] = []

    for material in materials:

        for raw in (
            material.diffuse,
            material.specular,
            material.normal,
            *ShaderParamString(material.paramstring).values(),
        ):

            suffix = Path(_backslash(raw)).suffix.lower()

            if suffix not in _TEXTURE_SUFFIXES:

                continue

            _add_unique(result, seen, raw)

    return result


def _effect_libraries(materials: list[MaterialSidecar]) -> list[str]:

    seen: set[str] = set()
    result: list[str] = []

    for material in materials:

        if not material.shader_library_stem:

            continue

        _add_unique(
            result,
            seen,
            f"Shaders\\{material.shader_library_stem}.ShaderLib",
        )

    return result
