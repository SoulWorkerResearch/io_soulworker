from __future__ import annotations

from collections.abc import Callable
from logging import debug
from pathlib import Path

import bpy
from bpy.types import Material, ShaderNodeBsdfPrincipled, ShaderNodeTexImage

from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.core.vis_transparency_type import VisTransparencyType


def specular_ior_level(spec_mul: float) -> float:
    """Map Vision ``spec_mul`` onto Principled *Specular IOR Level* (0..1)."""

    return max(0.0, min(1.0, spec_mul))


def roughness_from_spec_exp(spec_exp: float) -> float:
    """Phong exponent → Beckmann roughness: ``sqrt(2 / (n + 2))``."""

    return (2.0 / (max(spec_exp, 0.0) + 2.0)) ** 0.5


def apply_surface_params(
        material: Material,
        principled: ShaderNodeBsdfPrincipled,
        chunk: MtrsChunk,
        *,
        resolve_texture: Callable[[str], Path | None],
) -> None:
    """Drive Principled BSDF from ``MTRS`` Phong / map fields."""

    node_tree = material.node_tree

    if node_tree is None:

        return

    spec = specular_ior_level(chunk.spec_mul)
    roughness = roughness_from_spec_exp(chunk.spec_exp)

    principled.inputs["Specular IOR Level"].default_value = spec
    principled.inputs["Roughness"].default_value = roughness

    spec_map = _add_image_node(
        material,
        resolve_texture,
        chunk.specular_map,
        name="Specular",
        non_color=True,
    )

    if spec_map is not None:

        math_node = node_tree.nodes.new("ShaderNodeMath")
        math_node.name = "Specular Scale"
        math_node.label = "Specular Scale"
        math_node.operation = "MULTIPLY"
        math_node.inputs[1].default_value = spec
        node_tree.links.new(spec_map.outputs["Color"], math_node.inputs[0])
        node_tree.links.new(
            math_node.outputs["Value"],
            principled.inputs["Specular IOR Level"],
        )

    normal_map = _add_image_node(
        material,
        resolve_texture,
        chunk.normal_map,
        name="Normal",
        non_color=True,
    )

    if normal_map is not None:

        normal_node = node_tree.nodes.new("ShaderNodeNormalMap")
        normal_node.name = "Normal Map"
        normal_node.label = "Normal Map"
        node_tree.links.new(
            normal_map.outputs["Color"],
            normal_node.inputs["Color"],
        )
        node_tree.links.new(
            normal_node.outputs["Normal"],
            principled.inputs["Normal"],
        )

    _apply_transparency(material, chunk)


def _add_image_node(
        material: Material,
        resolve_texture: Callable[[str], Path | None],
        relative: str,
        *,
        name: str,
        non_color: bool,
) -> ShaderNodeTexImage | None:

    if not relative:

        return None

    node_tree = material.node_tree

    if node_tree is None:

        return None

    path = resolve_texture(relative)

    if path is None:

        return None

    node: ShaderNodeTexImage = node_tree.nodes.new("ShaderNodeTexImage")
    node.name = name
    node.label = name
    node.image = bpy.data.images.load(
        str(path),
        check_existing=True,
    )

    if non_color and node.image is not None:

        node.image.colorspace_settings.name = "Non-Color"

    debug("%s texture: %s", name, path)
    return node


def _apply_transparency(material: Material, chunk: MtrsChunk) -> None:

    threshold = chunk.custom_alpha_threshold

    if chunk.transparency_type == VisTransparencyType.NONE:

        material.blend_method = "OPAQUE"
        return

    if chunk.transparency_type == VisTransparencyType.ALPHATEST:

        # Blender 5 EEVEE Next remaps CLIP to HASHED; threshold still applies.
        material.blend_method = "CLIP"

        if threshold >= 0.0:

            material.alpha_threshold = threshold

        return

    material.blend_method = "BLEND"

    if threshold >= 0.0:

        material.alpha_threshold = threshold
