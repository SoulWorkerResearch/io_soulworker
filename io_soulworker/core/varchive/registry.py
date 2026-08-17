from __future__ import annotations

from io_soulworker.core.varchive.objects import (
    ArchiveObject,
    LightSource,
    Object3D,
    StaticMeshInstance,
)
from io_soulworker.core.varchive.reader import SerializeFn, VArchiveReader

# GamePlugin entities that serialize as ``VisBaseEntity_cl`` with no extra
# archive fields (no ``Serialize`` override in the plugin).
GAMEPLUGIN_BASE_ENTITIES = frozenset({
    "VEventBox",
    "VStartEventBox",
    "VMonsterSpawnBox",
    "VCheckMonsterSpawnBox",
    "VOpenMazeBox",
    "VCheckSceneDirectingBox",
    "VPortalBox",
    "VPortalExitBox",
    "VCommonPositionBox",
    "VSectorBox",
    "VCheckSectorBox",
    "VServerGateBox",
    "VMazeEscapeBox",
    "VLuaFunctionBox",
    "VInterActionBox",
    "VQuestMoveCheckBox",
    "VCutSceneEventBox",
    "VCheckEventSpawnBox",
    "VPersonalShopAreaBox",
    "VSafeAreaBox",
    "VSectorStartBox",
    "VSocialItemExcludeBox",
    "VCollisionEventBox",
    "VEventObject",
    "VEventPoint",
    "VWayPoint",
    "VEscortPoint",
    "VEventObjectShader",
    "VGateEntity_cl",
    "VIncludingShaderObject_cl",
    "VRigidBodyEntity",
    "VPartsEntity",
    "VAlphaStaticEntity_cl",
    "VCharLightColorCorrectionEntity_cl",
    "VCinematicCameraTester_cl",
})


def create_object(class_name: str) -> ArchiveObject:

    if class_name == "VisStaticMeshInstance_cl":
        return StaticMeshInstance()

    if class_name == "VisLightSource_cl":
        return LightSource()

    if class_name in (
        "VisObject3D_cl",
        "VisBaseEntity_cl",
        "CubeMapHandle_cl",
        "CameraPositionEntity",
        "VFogObject",
        "VSunGlare",
        "VisVisibilityObjectAABox_cl",
        "VProjectedWallmark",
        "VolumetricCone_cl",
        "VElectronicDisplay_cl",
        "VFmodEvent",
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
        "StaticCollisionEntity_cl",
        "VisMirror_cl",
        "PlanarWater_cl",
        "DisplacementWater_cl",
        "AnimEntity_cl",
        "ClothEntity_cl",
        "VCinematicActor_cl",
        "VisPath_cl",
        "VCustomVolumeObject",
        "VSkeletalBoneProxyObject",
    ) or class_name in GAMEPLUGIN_BASE_ENTITIES:
        return Object3D(class_name)

    return ArchiveObject(class_name)


def build_serializers() -> dict[str, SerializeFn]:

    from io_soulworker.core.varchive import serializers as ser

    serializers: dict[str, SerializeFn] = {
        "VisTypedEngineObject_cl": ser.serialize_typed_engine_object,
        "VisVisibilityZone_cl": ser.serialize_visibility_zone,
        "VisVisibilityZoneProxy_cl": ser.serialize_visibility_zone_proxy,
        "VisVisibilityObjectAABox_cl": ser.serialize_visibility_object,
        "VSky": ser.serialize_sky,
        "VForwardRenderingSystem": ser.serialize_forward_rendering_system,
        "VFakeGlowPostProcess": ser.serialize_fake_glow_post_process,
        "VPostProcessToneMapping": ser.serialize_tone_mapping,
        "VCopyPostProcess": ser.serialize_copy_post_process,
        "VSimpleCopyPostprocess": ser.serialize_simple_copy_post_process,
        "VRadialBlur": ser.serialize_radial_blur,
        "VPostProcessScreenFilter": ser.serialize_post_process_screen_filter,
        "VPostProcessOutline": ser.serialize_post_process_outline,
        "VTextureSerializationProxy": ser.serialize_texture_serialization_proxy,
        "VisStaticMeshInstance_cl": ser.serialize_static_mesh_instance,
        "VFogObject": ser.serialize_fog_object,
        "VisLightSource_cl": ser.serialize_light_source,
        "VShadowMapComponentSpotDirectional": ser.serialize_shadow_map_spot,
        "CameraPositionEntity": ser.serialize_camera_position_entity,
        "VisBaseEntity_cl": ser.serialize_base_entity,
        "CubeMapHandle_cl": ser.serialize_cube_map_handle,
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
        "StaticCollisionEntity_cl": ser.serialize_static_collision_entity,
        "VisMirror_cl": ser.serialize_mirror,
        "PlanarWater_cl": ser.serialize_planar_water,
        "DisplacementWater_cl": ser.serialize_displacement_water,
        "AnimEntity_cl": ser.serialize_anim_entity,
        "ClothEntity_cl": ser.serialize_cloth_entity,
        "VCinematicActor_cl": ser.serialize_cinematic_actor,
        "VisPath_cl": ser.serialize_path,
        "VCustomVolumeObject": ser.serialize_custom_volume_object,
        "VSkeletalBoneProxyObject": ser.serialize_skeletal_bone_proxy,
        "VDirectingOfPrefabComponent": ser.serialize_directing_prefab_component,
        "VDirectingOfEntityComponent": ser.serialize_directing_entity_component,
        "vHavokRigidBody": ser.serialize_havok_rigid_body,
        "VCharacterParticleComponent": ser.serialize_character_particle_component,
        "VFollowPathComponent": ser.serialize_follow_path_component,
        "VLightClippingVolumeComponent": ser.serialize_light_clipping_volume_component,
        "VScriptComponent": ser.serialize_script_component,
        "VFmodEvent": ser.serialize_fmod_event,
        "vHavokAiNavMeshInstance": ser.serialize_havok_ai_nav_mesh,
        "VSunGlare": ser.serialize_sun_glare,
        "VSimpleAnimationComponent": ser.serialize_simple_animation_component,
        "VSkeletonSerializationProxy": ser.serialize_skeleton_serialization_proxy,
        "VisVertexDeformerStack_cl": ser.serialize_vertex_deformer_stack,
        "VisSkinningDeformer_cl": ser.serialize_skinning_deformer,
        "VisAnimFinalSkeletalResult_cl": ser.serialize_anim_final_skeletal_result,
        "VisSkeletalAnimControl_cl": ser.serialize_skeletal_anim_control,
        "VisAnimConfig_cl": ser.serialize_anim_config,
    }

    for name in GAMEPLUGIN_BASE_ENTITIES:
        serializers[name] = ser.serialize_base_entity

    serializers["VGateEntity_cl"] = ser.serialize_gate_entity

    return serializers


# Empty: remaining unknown classes still skip by object length when
# ``use_object_lengths`` is set. Do not add classes that embed ReadObject.
LEAF_SKIP_CLASSES: set[str] = set()


ALIASES: dict[str, str] = {}
