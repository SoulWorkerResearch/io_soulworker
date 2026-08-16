from __future__ import annotations

from io_soulworker.core.varchive.objects import (
    ArchiveObject,
    LightSource,
    Object3D,
    StaticMeshInstance,
)
from io_soulworker.core.varchive.reader import SerializeFn, VArchiveReader


def create_object(class_name: str) -> ArchiveObject:

    if class_name == "VisStaticMeshInstance_cl":
        return StaticMeshInstance()

    if class_name == "VisLightSource_cl":
        return LightSource()

    if class_name in (
        "VisObject3D_cl",
        "VisBaseEntity_cl",
        "CameraPositionEntity",
        "VFogObject",
    ):
        return Object3D(class_name)

    return ArchiveObject(class_name)


def build_serializers() -> dict[str, SerializeFn]:

    from io_soulworker.core.varchive import serializers as ser

    return {
        "VisTypedEngineObject_cl": ser.serialize_typed_engine_object,
        "VisVisibilityZone_cl": ser.serialize_visibility_zone,
        "VSky": ser.serialize_sky,
        "VForwardRenderingSystem": ser.serialize_forward_rendering_system,
        "VFakeGlowPostProcess": ser.serialize_fake_glow_post_process,
        "VPostProcessToneMapping": ser.serialize_tone_mapping,
        "VCopyPostProcess": ser.serialize_copy_post_process,
        "VisStaticMeshInstance_cl": ser.serialize_static_mesh_instance,
        "VFogObject": ser.serialize_fog_object,
        "VisLightSource_cl": ser.serialize_light_source,
        "VShadowMapComponentSpotDirectional": ser.serialize_shadow_map_spot,
        "CameraPositionEntity": ser.serialize_camera_position_entity,
        "VisBaseEntity_cl": ser.serialize_base_entity,
        "VTimeOfDay": ser.serialize_time_of_day,
        "VTimeOfDayComponent": ser.serialize_time_of_day_component,
        "VCoronaComponent": ser.serialize_corona_component,
    }


# Classes with no nested ReadObject in current fixtures (or remaining
# fields are opaque). Safe only when object lengths are enabled (SCNE >= 13).
LEAF_SKIP_CLASSES = {
    "VFakeGlowPostProcess",
    "VCopyPostProcess",
    "VSimpleCopyPostprocess",
    "VTimeOfDay",
    "VTimeOfDayComponent",
    "VCoronaComponent",
}


# LoginBackground names the copy PP ``VCopyPostProcess``.
ALIASES: dict[str, str] = {}
