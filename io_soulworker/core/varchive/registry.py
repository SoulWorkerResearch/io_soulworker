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
        "VInterActionBox",
        "VSunGlare",
        "VisVisibilityObjectAABox_cl",
        "VProjectedWallmark",
        "VolumetricCone_cl",
        "VElectronicDisplay_cl",
        "VisParticleConstraint_cl",
        "VisParticleConstraintAABox_cl",
        "VisParticleConstraintOBox_cl",
        "VisParticleConstraintPoint_cl",
        "VisParticleConstraintPlane_cl",
        "VisParticleConstraintSphere_cl",
        "VisParticleConstraintCamBox_cl",
        "VisParticleConstraintInfCylinder_cl",
        "VisParticleConstraintGroundPlane_cl",
        "VisParticleConstraintTerrain_cl",
        "VisParticleAffectorFan_cl",
        "VisParticleAffectorCyclone_cl",
        "VisParticleAffectorGravityPoint_cl",
        "VisParticleEffect_cl",
        "VSectorBox",
        "StaticCollisionEntity_cl",
    ):
        return Object3D(class_name)

    return ArchiveObject(class_name)


def build_serializers() -> dict[str, SerializeFn]:

    from io_soulworker.core.varchive import serializers as ser

    return {
        "VisTypedEngineObject_cl": ser.serialize_typed_engine_object,
        "VisVisibilityZone_cl": ser.serialize_visibility_zone,
        "VisVisibilityZoneProxy_cl": ser.serialize_visibility_zone_proxy,
        "VisVisibilityObjectAABox_cl": ser.serialize_visibility_object,
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
        "VModelSerializationProxy": ser.serialize_model_serialization_proxy,
        "VSequenceSetSerializationProxy": ser.serialize_sequence_set_proxy,
        "VSequenceSerializationProxy": ser.serialize_sequence_proxy,
        "VProjectedWallmark": ser.serialize_projected_wallmark,
        "VStaticMeshAlphaController": ser.serialize_static_mesh_alpha_controller,
        "VSurfaceTextureSetSerializationProxy": ser.serialize_surface_texture_set_proxy,
        "VolumetricCone_cl": ser.serialize_volumetric_cone,
        "VElectronicDisplay_cl": ser.serialize_electronic_display,
        "VisParticleConstraint_cl": ser.serialize_particle_constraint,
        "VisParticleConstraintGroundPlane_cl": ser.serialize_particle_constraint,
        "VisParticleConstraintInfCylinder_cl": ser.serialize_particle_constraint,
        "VisParticleConstraintAABox_cl": ser.serialize_particle_constraint_obox,
        "VisParticleConstraintOBox_cl": ser.serialize_particle_constraint_obox,
        "VisParticleConstraintPoint_cl": ser.serialize_particle_constraint_point,
        "VisParticleConstraintPlane_cl": ser.serialize_particle_constraint_plane,
        "VisParticleConstraintSphere_cl": ser.serialize_particle_constraint_sphere,
        "VisParticleConstraintCamBox_cl": ser.serialize_particle_constraint_cambox,
        "VisParticleConstraintTerrain_cl": ser.serialize_particle_constraint_terrain,
        "VisParticleAffectorFan_cl": ser.serialize_particle_affector_fan,
        "VisParticleAffectorCyclone_cl": ser.serialize_particle_affector_fan,
        "VisParticleAffectorGravityPoint_cl": ser.serialize_particle_affector_gravity,
        "VisParticleEffect_cl": ser.serialize_particle_effect,
        "VSectorBox": ser.serialize_sector_box,
        "StaticCollisionEntity_cl": ser.serialize_static_collision_entity,
        "VInterActionBox": ser.serialize_base_entity,
        "VSunGlare": ser.serialize_sun_glare,
        "VSimpleAnimationComponent": ser.serialize_simple_animation_component,
        "VSkeletonSerializationProxy": ser.serialize_skeleton_serialization_proxy,
        "VisVertexDeformerStack_cl": ser.serialize_vertex_deformer_stack,
        "VisSkinningDeformer_cl": ser.serialize_skinning_deformer,
        "VisAnimFinalSkeletalResult_cl": ser.serialize_anim_final_skeletal_result,
        "VisSkeletalAnimControl_cl": ser.serialize_skeletal_anim_control,
        "VisAnimConfig_cl": ser.serialize_anim_config,
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
    "VStaticMeshAlphaController",
    "VScriptComponent",
    "VFmodEvent",
    "VSequenceSetSerializationProxy",
    "vHavokAiNavMeshInstance",
    "vHavokRigidBody",
}


# LoginBackground names the copy PP ``VCopyPostProcess``.
ALIASES: dict[str, str] = {}
