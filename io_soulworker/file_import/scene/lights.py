"""Blender light objects for the ``VisLightSource_cl`` objects of a scene.

Type, colour, reach and cone angle follow the archive. Brightness does not:
a Vision multiplier has no unit, so the power below is an approximation that
puts a light of multiplier 1.0 at about full brightness on a white surface.
"""

from __future__ import annotations

from logging import warning
from math import isfinite, pi, radians

import bpy
from bpy.types import Collection, Object
from mathutils import Matrix

from ...core.varchive.objects import LightSource
from ...file_import.scene.id_properties import blender_id_int32
from ...unit_scale import vision_to_blender


BLENDER_LIGHT_TYPES = {
    LightSource.TYPE_POINT: "POINT",
    LightSource.TYPE_DIRECTIONAL: "SUN",
    LightSource.TYPE_SPOTLIGHT: "SPOT",
}

SUN_STRENGTH_PER_MULTIPLIER = pi
"""Sun strength (W/m²) per unit of multiplier.

An irradiance of pi W/m² lights a white surface facing the sun to radiance 1.
"""

POINT_WATTS_PER_SQUARE_METRE = pi ** 3
"""Point and spot power (W) per unit of multiplier and square metre of radius.

A Blender point light of P watts gives a facing surface at distance d an
irradiance of P / (4 pi^2 d^2) W/m². Asking for pi W/m² at half the radius
gives P = pi^3 r^2, so lights of different reach look alike at the same
relative distance.
"""

MIN_SPOT_SIZE = radians(1.0)
LIGHT_COLLECTION_NAME = "Lights"


def srgb_to_linear(value: float) -> float:

    if value <= 0.04045:
        return value / 12.92

    return ((value + 0.055) / 1.055) ** 2.4


def light_color(light: LightSource) -> tuple[float, float, float]:
    """The archive's colour bytes as sRGB, converted to Blender's linear RGB."""

    return tuple(srgb_to_linear(byte / 255.0) for byte in light.rgb)


def light_energy(light: LightSource) -> float:
    """Sun strength or watts for a light; see the constants above."""

    multiplier = light.multiplier if isfinite(light.multiplier) else 0.0
    multiplier = max(multiplier, 0.0)

    if light.light_type == LightSource.TYPE_DIRECTIONAL:
        return multiplier * SUN_STRENGTH_PER_MULTIPLIER

    radius = max(vision_to_blender(light.radius), 0.0)

    if not isfinite(radius):
        return 0.0

    return multiplier * POINT_WATTS_PER_SQUARE_METRE * radius * radius


def light_world_matrix(placement: Matrix) -> Matrix:
    """Blender world matrix of a light placed like an entity.

    Vision lights shine along the +Y axis of the entity matrix (suns and
    street lamps point down in the game scenes), Blender lights along -Z.
    """

    return placement @ Matrix.Rotation(radians(90.0), 4, "X")


def create_light_object(
    light: LightSource,
    collection: Collection,
    placement: Matrix,
) -> Object | None:
    """Link a Blender light for ``light`` into ``collection``.

    ``placement`` is the light's Vision position and orientation as a Blender
    matrix. Returns ``None`` for a light type that has no Blender counterpart.
    """

    kind = BLENDER_LIGHT_TYPES.get(light.light_type)

    if kind is None:
        warning("Skipping light of unknown type %d", light.light_type)
        return None

    name = light.object_key or kind.title()
    data = bpy.data.lights.new(name, kind)
    data.color = light_color(light)
    data.energy = light_energy(light)
    radius = vision_to_blender(light.radius)

    if kind != "SUN" and isfinite(radius) and radius > 0.0:
        data.use_custom_distance = True
        data.cutoff_distance = radius

    if kind == "SPOT":
        angle = radians(light.spot_angle) if isfinite(light.spot_angle) else pi
        data.spot_size = min(max(angle, MIN_SPOT_SIZE), pi)

    obj = bpy.data.objects.new(name, data)
    obj.matrix_world = light_world_matrix(placement)
    collection.objects.link(obj)

    obj["soulworker_class"] = light.class_name
    obj["soulworker_light_type"] = light.light_type
    obj["soulworker_radius"] = light.radius
    obj["soulworker_multiplier"] = light.multiplier
    obj["soulworker_color"] = blender_id_int32(light.color)
    obj["soulworker_spot_angle"] = light.spot_angle
    obj["soulworker_fade_start"] = light.fade_start
    obj["soulworker_fade_end"] = light.fade_end
    obj["soulworker_visible_mask"] = blender_id_int32(light.visible_mask)
    obj["soulworker_world_influence_mask"] = blender_id_int32(
        light.world_influence_mask)
    obj["soulworker_object_influence_mask"] = blender_id_int32(
        light.object_influence_mask)
    obj["soulworker_flags"] = light.flags
    obj["soulworker_cast_shadows"] = light.cast_shadows

    if light.projected_texture:
        obj["soulworker_projected_texture"] = light.projected_texture

    if light.attenuation_texture:
        obj["soulworker_attenuation_texture"] = light.attenuation_texture

    # No render context shows a light whose visible mask is zero.
    if light.visible_mask == 0:
        obj.hide_viewport = True
        obj.hide_render = True

    return obj
