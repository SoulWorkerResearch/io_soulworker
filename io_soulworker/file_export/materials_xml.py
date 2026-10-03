from __future__ import annotations

from dataclasses import dataclass
from os.path import relpath
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, indent

from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.core.vis_color import VisColor
from io_soulworker.core.vis_lighting_method import VisLightingMethod
from io_soulworker.core.vis_material_effect import VisMaterialEffect
from io_soulworker.core.vis_material_lighting import VisMaterialLighting
from io_soulworker.core.vis_surface_flags import VisSurfaceFlags
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.core.xml_helper.exchange_transparency import (
    transparency_to_exchange,
)


DEFAULT_DIFFUSE = r"\PlainWhite.DDS"


def materials_xml_path(mesh_path: Path) -> Path:
    """``Foo.model`` → ``Foo.model_data/materials.xml``."""

    return mesh_path.parent / f"{mesh_path.name}_data" / "materials.xml"


def format_xml_float(value: float) -> str:
    """Compact decimal for materials.xml numeric attributes."""

    number = float(value)

    if number != number or number in (float("inf"), float("-inf")):

        return "0"

    text = f"{number:.6f}".rstrip("0").rstrip(".")

    if text in {"", "-0"}:

        return "0"

    return text


def shader_library_xml_path(
        library_stem: str,
        materials_xml: Path,
        resources_root: Path | None) -> str:

    filename = f"{library_stem}.ShaderLib"

    if resources_root is not None:

        target = Path(resources_root) / "Shaders" / filename

        try:

            return relpath(target, materials_xml.parent).replace("/", "\\")

        except ValueError:

            pass

    return f"Shaders\\{filename}"


@dataclass
class MaterialSidecar:
    """Blender-side material fields written to MTRS and materials.xml."""

    name: str
    diffuse: str = DEFAULT_DIFFUSE
    specular: str = ""
    normal: str = ""
    transparency: VisTransparencyType = VisTransparencyType.NONE
    doublesided: bool = False
    depthwrite: bool = True
    spec_mul: float = 0.0
    spec_exp: float = 2.0
    parallax_scale: float = -0.03
    parallax_bias: float = -0.015
    ambient: tuple[int, int, int, int] = (0, 0, 0, 255)
    sorting_key: int = 0
    alphathreshold: float = -1.0
    lighting: str = VisMaterialLighting.NONE.value
    user_flags: int = 0
    shader_library_stem: str = ""
    shader_effect: str = ""
    paramstring: str = ""

    def shader_library_binary(self) -> str:

        if not self.shader_library_stem:

            return ""

        return f"Shaders\\{self.shader_library_stem}.ShaderLib"

    def to_mtrs_chunk(self) -> MtrsChunk:

        material = MtrsChunk()
        material._envelope_enter_depth = 1
        material.version = 6
        material.name = self.name or "default"
        material.flags = VisSurfaceFlags.NONE
        material.lighting_method = VisLightingMethod.FULLBRIGHT
        material.ui_sorting_key = min(max(int(self.sorting_key), 0), 15)
        material.spec_mul = self.spec_mul
        material.spec_exp = self.spec_exp
        material.transparency_type = self.transparency
        material.ui_deferred_id = 0
        material.depth_bias = 0.0
        material.depth_bias_clamp = 0.0
        material.slope_scaled_depth_bias = 0.0
        material.custom_alpha_threshold = self.alphathreshold
        material.diffuse_map = self.diffuse or DEFAULT_DIFFUSE
        material.specular_map = self.specular
        material.normal_map = self.normal
        material.aux_texture_paths = []
        material.user_data = ""
        material.user_flags = self.user_flags
        material.ambient_color = VisColor(*self.ambient)
        material.brightness = 0
        material.light_color = VisColor(0, 0, 0, 0)
        material.parallax_scale = self.parallax_scale
        material.parallax_bias = self.parallax_bias
        material.override_library = ""
        material.override_material = ""
        material.ui_mobile_shader_flags = 0

        effect = VisMaterialEffect()
        effect.library = self.shader_library_binary()
        effect.name = self.shader_effect
        effect.param = self.paramstring
        material.config_effects = [effect]

        return material


def write_materials_xml(
        path: Path,
        materials: list[MaterialSidecar],
        resources_root: Path | None = None) -> Path:
    """Write ``{mesh}.model_data/materials.xml`` (or ``.vmesh_data``)."""

    path.parent.mkdir(parents=True, exist_ok=True)

    root = Element("root")
    container = Element("Materials", {"override": "TRUE"})
    root.append(container)

    for material in materials:

        attrib = {
            "name": material.name,
            "diffuse": material.diffuse or DEFAULT_DIFFUSE,
            "Lighting": material.lighting or VisMaterialLighting.NONE.value,
            "transparency": transparency_to_exchange(material.transparency),
            "doublesided": "TRUE" if material.doublesided else "FALSE",
            "depthwrite": "TRUE" if material.depthwrite else "FALSE",
            "zbias": "0,0,0",
            "specmul": format_xml_float(material.spec_mul),
            "specexp": format_xml_float(material.spec_exp),
            "parallaxscale": format_xml_float(material.parallax_scale),
            "parallaxbias": format_xml_float(material.parallax_bias),
            "ambient": ",".join(str(int(component))
                                for component in material.ambient),
            "sortingkey": str(int(material.sorting_key)),
            "alphathreshold": format_xml_float(material.alphathreshold),
            "lightmapsize": "128,128",
            "lightmapgran": "0",
            "lightmapID": "-1",
        }

        node = Element("Material", attrib)

        if material.shader_effect and material.shader_library_stem:

            node.append(
                Element(
                    "Shader",
                    {
                        "library": shader_library_xml_path(
                            material.shader_library_stem,
                            path,
                            resources_root,
                        ),
                        "effect": material.shader_effect,
                        "paramstring": material.paramstring,
                    },
                )
            )

        container.append(node)

    indent(root, space="    ")
    tree = ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=False)

    data = path.read_bytes()

    if not data.endswith(b"\n"):

        path.write_bytes(data + b"\n")

    return path
