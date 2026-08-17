from __future__ import annotations

from io_soulworker.core.varchive.objects import (
    ArchiveObject,
    LightSource,
    Object3D,
    StaticMeshInstance,
)
from io_soulworker.core.varchive.reader import VArchiveError, VArchiveReader


def serialize_components(ar: VArchiveReader, owner: ArchiveObject) -> None:
    """``VObjectComponentCollection::SerializeX`` (loading)."""

    version = ar.read_uint8()
    count = ar.read_int32()

    for _ in range(count):
        mode = 0

        if version >= 1:
            mode = ar.read_uint8()

        if mode == 0:
            component = ar.read_object()

            if component is not None:
                owner.components.append(component)
        else:
            # Owner ref + component id, then inline Serialize of an existing
            # component (already in the collection). We only need the bytes.
            ar.read_object()  # owner (unused)
            ar.read_int32()  # component id (unused)
            raise VArchiveError(
                "component serialize-mode 1 (by id) is not implemented"
            )


def serialize_typed_engine_object(
        ar: VArchiveReader,
        obj: ArchiveObject) -> int:
    """``VisTypedEngineObject_cl::Serialize`` (loading, archive >= 28).

    Returns the local version byte, or ``-1`` when the block is absent.
    """

    if ar.loading_version < 28:
        return -1

    local_version = ar.read_uint8()

    if local_version >= 1:
        serialize_components(ar, obj)

    if local_version >= 2:
        obj.unique_id = ar.read_int64()

    return local_version


def serialize_object_component_base(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``IVObjectComponent::Serialize`` (loading)."""

    serialize_typed_engine_object(ar, obj)
    version = ar.read_uint8()
    ar.read_object()  # owner (discarded by engine too)
    ar.read_int32()  # component flags (unused)

    if version >= 1:
        # SerializeComponentID — either string name or int id
        if ar.read_bool():
            ar.read_string_binary()  # component id string (unused)
        else:
            ar.read_int32()  # component id int (unused)


def _serialize_visibility_data(ar: VArchiveReader) -> dict:
    """``VVisibilityData::Serialize_VisData``."""

    vis_version = ar.read_uint8()
    ar.read_bbox_x()  # bounding box
    ar.read_vec3()  # frustum hint / center
    visible_mask = ar.read_uint32()  # m_iVisibleMask
    ar.read_float()  # m_fFarClipDistance
    perform_test_flags = ar.read_int32()  # m_iPerformTestFlags
    ar.read_float()  # m_fNearClipDistance

    return {
        "vis_version": vis_version,
        "visible_mask": visible_mask,
        "perform_test_flags": perform_test_flags,
    }


def _serialize_effect_config(ar: VArchiveReader) -> None:
    """``VisEffectConfig_cl::ReadFromStream`` via archive — unused."""

    tech_count = ar.read_uint16()

    for _ in range(tech_count):
        ar.read_string_binary()  # technique name
        ar.read_string_binary()  # effect / library
        ar.read_string_binary()  # parameter block
        ar.read_int32()  # technique flags


def _read_zone_exchange(ar: VArchiveReader) -> ArchiveObject | None:
    """``VisVisibilityZone_cl::DoArchiveExchange`` (loading)."""

    if ar.read_bool():
        return ar.read_proxy_object()

    return ar.read_object()


def serialize_visibility_zone_proxy(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisVisibilityZoneProxy_cl::Serialize`` (loading)."""

    ar.read_uint8()  # local version
    ar.read_int64()  # zone unique id


def serialize_visibility_object(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisVisibilityObject_cl::Serialize`` (loading)."""

    assert isinstance(obj, Object3D)
    serialize_object3d(ar, obj)
    version = ar.read_uint8()

    if version >= 3:
        _serialize_visibility_data(ar)

    ar.read_int32()  # flags
    ar.read_bool()  # bounding box set

    if version >= 2:
        ar.read_bool()  # world-space bbox

    ar.read_bbox_vis()  # local AABB

    if version < 3:
        ar.read_bbox_vis()  # world AABB

    ar.read_uint8()  # reschedule mask

    if version < 3:
        ar.read_float()  # far clip

    ar.read_int32()  # pixel threshold


def _serialize_object3d_vis_data(ar: VArchiveReader) -> None:
    """``VisObject3DVisData_cl::SerializeX`` (loading) — unused."""

    ar.read_uint8()  # vis-data local version
    ar.read_object()  # owner Object3D
    ar.read_bool()  # use custom frustum / clip
    ar.read_vis_vector()  # clip plane / offset
    ar.read_float()  # clip distance

    for _ in range(ar.read_int16()):
        _read_zone_exchange(ar)  # zone membership (map sync only)


def serialize_object3d(ar: VArchiveReader, obj: Object3D) -> None:
    """``VisObject3D_cl::Serialize`` (loading, archive >= 12)."""

    if ar.loading_version >= 12:
        serialize_typed_engine_object(ar, obj)

    local_version = 0

    if ar.loading_version >= 21:
        local_version = ar.read_uint8()

        if 1 <= local_version <= 5:
            obj.unique_id = ar.read_int64()

    obj.position = ar.read_vis_vector()
    obj.orientation = ar.read_vis_vector()
    ar.read_vis_vector()  # local / relative orientation (unused)

    if local_version >= 5:
        ar.read_vis_vector()  # scale (unused)

    ar.read_vis_vector()  # euler / direction leftover (unused)

    if ar.loading_version >= 25:
        obj.object_key = ar.read_vstring()

    if local_version >= 7:
        ar.read_int32()  # object status / misc flags (unused)

    if ar.loading_version < 12:
        ar.read_vec3()  # legacy position (unused; superseded by VisVector)

    if local_version < 1:
        ar.read_int32()  # legacy unique-id low bits (unused)

    if ar.loading_version >= 7:
        flags = ar.read_uint32()

        if (flags & 0x20) == 0:
            ar.read_mat3()  # local rotation matrix (unused)

    if ar.loading_version >= 10:
        ar.read_object()  # parent Object3D (map sync only)

    if local_version >= 2 and ar.loading_version < 28:
        serialize_components(ar, obj)

    if local_version >= 4 and ar.read_bool():
        _serialize_object3d_vis_data(ar)


def serialize_visibility_zone(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VisVisibilityZone_cl::Serialize`` (loading)."""

    serialize_typed_engine_object(ar, obj)
    version = ar.read_uint8()

    if 2 <= version <= 3:
        ar.read_int64()  # legacy unique id (unused; TypedEngine has it ≥28)

    flags = ar.read_uint32()
    ar.read_uint32()  # zone type / status bits (unused)
    ar.read_bbox_vis()  # zone AABB (unused)

    if version >= 3:
        ar.read_bbox_vis()  # secondary / expanded AABB (unused)

    ar.read_color_ref()  # debug color (unused)

    if (flags & 1) != 0:
        for _ in range(ar.read_uint16()):
            raise VArchiveError("VisPortal_cl not implemented")

    if (flags & 2) != 0:
        for _ in range(ar.read_uint16()):
            ar.read_object()  # static geometry / mesh ref (map sync only)

    if (flags & 0x100) != 0:
        # CharacterSelect remainder is a 16-bit zero count.
        for _ in range(ar.read_uint16()):
            ar.read_uint32()  # extra zone tag / bitmask (unused)


def serialize_sky(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VSky::Serialize`` — layer/effect fields unused by importer."""

    ar.read_int32()  # sky flags / mode
    ar.read_int32()  # sky type
    ar.read_uint32()  # render flags
    layer_count = ar.read_int32()

    for _ in range(layer_count):
        ar.read_uint8()  # layer type
        ar.read_uint8()  # layer flags
        ar.read_vec4()  # color / tint
        ar.read_vec4()  # scroll / UV speed
        ar.read_vec4()  # scale / bias
        ar.read_vec2()  # rotation / phase
        ar.read_string_binary()  # layer texture

        for _ in range(6):
            ar.read_string_binary()  # cubemap face paths

    _serialize_effect_config(ar)


def serialize_forward_rendering_system(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VForwardRenderingSystem::Serialize`` — config unused by importer."""

    local_version = ar.read_uint8()
    ar.read_int32()  # context / flags
    ar.read_int32()  # MSAA samples
    ar.read_int32()  # render targets / buffer flags

    if 1 <= local_version <= 3:
        ar.read_int32()  # legacy quality enum

    if local_version >= 2:
        ar.read_int32()  # depth / HDR related

    if local_version >= 3:
        ar.read_int32()  # extra renderer flags

    serialize_typed_engine_object(ar, obj)


def serialize_fake_glow_post_process(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:

    raise VArchiveError("VFakeGlowPostProcess should be leaf-skipped")


def serialize_tone_mapping(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VPostProcessToneMapping::Serialize`` (loading)."""

    local_version = ar.read_uint8()
    ar.read_bool()  # active
    ar.read_mat4()  # color grading / tone matrix (unused)
    ar.read_int32()  # operator / mode

    if local_version >= 1:
        ar.read_proxy_object()  # optional LUT / texture proxy (map sync)

    ar.read_float()  # exposure
    ar.read_float()  # gamma
    ar.read_float()  # saturation
    ar.read_float()  # contrast
    ar.read_color_ref()  # tint
    ar.read_object()  # renderer back-ref


def serialize_copy_post_process(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VSimpleCopyPostprocess`` / ``VCopyPostProcess`` wire (loading).

    LoginBackground names the class ``VCopyPostProcess``; the stock plugin
    type is ``VSimpleCopyPostprocess``. Both write active + renderer ref.
    """

    ar.read_bool()  # active
    ar.read_object()  # renderer


def serialize_static_geometry_instance(ar: VArchiveReader) -> dict:
    """``VisStaticGeometryInstance_cl::SerializeX`` (loading)."""

    version = ar.read_uint8()
    vis: dict = {}

    if version < 8:
        ar.read_float()  # legacy far clip / LOD

        if version >= 4:
            ar.read_float()  # legacy near / fade
            ar.read_vec3()  # legacy center
            ar.read_int32()  # legacy vis flags
    else:
        vis = _serialize_visibility_data(ar)

    geometry_type = ar.read_int32()

    if version < 8:
        ar.read_bbox_vis()  # local AABB (unused)

    light_mask = ar.read_uint32()

    # Stock Vision also writes trace mask here. CharacterSelect / login
    # fixtures (SGI v8) omit those 4 bytes — validated via object-length
    # checksum against the parent SMI payload. Zone files match that layout.
    if version < 8:
        ar.read_uint32()  # trace mask
        ar.read_uint32()  # visible (legacy)

    cast_shadows = ar.read_bool()  # m_bCastDynamicShadows
    sorting_key = ar.read_int32()  # m_iSortingKey (not collision flags)

    if version != 6:
        ar.read_int64()  # geometry unique id (unused)

    ar.read_bool()  # lit / lightmapped

    if version < 3:
        if version < 2:
            ar.read_object()  # single zone (map sync)
        else:
            _read_zone_exchange(ar)  # single zone exchange (map sync)
    else:
        for _ in range(ar.read_uint16()):
            _read_zone_exchange(ar)  # zone list (map sync)

    ar.read_vec4()  # lightmap / UV transform (unused)

    for _ in range(4):
        ar.read_string_binary()  # lightmap / material texture paths (unused)

    if version >= 1:
        for _ in range(ar.read_int16()):
            # VisShadowmap_cl::SerializeX
            sm_version = ar.read_uint8()
            by_id = ar.read_bool() if sm_version >= 1 else False

            if by_id:
                ar.read_int64()  # shadowmap unique id (unused)
            else:
                ar.read_object()  # shadowmap object (map sync)

            ar.read_vec4()  # shadow UV / bias (unused)
            ar.read_string_binary()  # shadow texture path (unused)

    if version >= 5:
        ar.read_object()  # surface / material owner (map sync)

    return {
        "geometry_type": geometry_type,
        "light_mask": light_mask,
        "cast_shadows": cast_shadows,
        "sorting_key": sorting_key,
        **vis,
    }


def serialize_static_mesh_instance(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisStaticMeshInstance_cl::Serialize`` (loading)."""

    assert isinstance(obj, StaticMeshInstance)
    serialize_typed_engine_object(ar, obj)

    obj.version = ar.read_uint8()
    obj.path = ar.read_string_binary()

    if obj.version < 3:
        obj.unique_id = ar.read_int64()

    obj.matrix = ar.read_mat4()
    ar.read_bbox_vis()  # world AABB (unused)
    ar.read_vec4()  # lightgrid sample / tint (unused)

    if ar.loading_version >= 25:
        obj.object_key = ar.read_vstring()

    # ... shows visibility level for iVersion >= 10; SW fixtures with
    # iVersion == 9 already include the int32 field.
    if obj.version >= 9:
        obj.visibility_level = ar.read_int32()

    if obj.version >= 1:
        if obj.version < 5:
            obj.light_mask = ar.read_uint16()
        else:
            obj.light_mask = ar.read_uint32()

    if obj.version >= 9:
        # Write path (iVersion 10) stores VisCollisionBehavior as uint32;
        # CharacterSelect (iVersion 9) stores a single uint8.
        if obj.version >= 10:
            obj.collision_behavior = ar.read_uint32()
        else:
            obj.collision_behavior = ar.read_uint8()

    # Physics hint appears with iVersion >= 10 (current write path).
    if obj.version >= 10:
        obj.physics_hint = ar.read_uint8()

    if ar.shallow_static_meshes and ar.current_payload_end is not None:
        ar.seek(ar.current_payload_end)
        return

    obj.geometries = [
        serialize_static_geometry_instance(ar)
        for _ in range(ar.read_int32())
    ]

    if obj.version >= 4:
        if obj.version < 8:
            if ar.read_bool():
                raise VArchiveError(
                    "inline VisSurfaceTextureSet not implemented")
        else:
            ar.read_proxy_object()  # surface texture set (map sync)


def serialize_fog_object(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VFogObject::Serialize`` — fog parameters unused by importer."""

    assert isinstance(obj, Object3D)
    serialize_object3d(ar, obj)

    version = ar.read_uint8()
    ar.read_uint8()  # fog mode / type
    _serialize_effect_config(ar)
    ar.read_uint8()  # density mode
    ar.read_bool()  # enabled
    ar.read_vis_vector()  # color
    ar.read_bool()  # use start/end
    ar.read_vis_vector()  # start
    ar.read_vis_vector()  # end
    ar.read_bool()  # use density curve
    ar.read_vis_vector()  # density params A
    ar.read_vis_vector()  # density params B
    ar.read_bool()  # height fog
    ar.read_vis_vector()  # height base
    ar.read_vis_vector()  # height falloff
    ar.read_vis_vector()  # height color

    if version >= 2:
        ar.read_bool()  # animated
        ar.read_string_binary()  # animation curve / texture
        ar.read_vis_vector()  # anim speed
        ar.read_vis_vector()  # anim amplitude

    if version >= 3:
        ar.read_uint8()  # quality / sample count


def _serialize_light_anim_intensity(ar: VArchiveReader) -> None:
    """``VisLightSrc_AnimIntensity_cl::SerializeX`` — unused."""

    ar.read_int32()  # anim type / flags
    ar.read_int32()  # mode
    ar.read_int32()  # key count / reserved

    for _ in range(7):
        ar.read_float()  # intensity curve keys / timing


def _serialize_light_anim_color(ar: VArchiveReader) -> None:
    """``VisLightSrc_AnimColor_cl::SerializeX`` — unused."""

    type_packed = ar.read_int32()
    ar.read_int32()  # mode
    ar.read_int32()  # reserved / phase
    ar.read_int32()  # reserved
    ar.read_int32()  # reserved

    for _ in range(3):
        ar.read_int32()  # channel enabled

    for _ in range(9):
        ar.read_int32()  # minC / maxC / curC

    for _ in range(6):
        ar.read_float()  # speed / time

    if ar.loading_version >= 6:
        ar.read_vstring()  # anim curve name (unused)
        ar.read_float()  # curve scale
        ar.read_float()  # curve offset
        ar.read_float()  # curve speed

        for _ in range(3):
            ar.read_uint8()  # per-channel curve flags

    if (type_packed >> 8) >= 1:
        ar.read_bool()  # use HSV / alternate mode


def serialize_light_source(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VisLightSource_cl::Serialize`` (loading, archive >= 12)."""

    assert isinstance(obj, LightSource)

    if ar.loading_version < 12:
        serialize_typed_engine_object(ar, obj)
    else:
        serialize_object3d(ar, obj)

    light_version = 0

    if ar.loading_version >= 21:
        light_version = ar.read_uint8()

    if ar.loading_version < 12:
        ar.read_uint16()  # legacy light flags
        ar.read_bool()  # legacy active
        ar.read_vec4()  # legacy color
        ar.read_mat3()  # legacy orientation
        ar.read_mat3()  # legacy scale / basis

    obj.intensity = ar.read_float()
    ar.read_int32()  # oldI index (... shows ushort; SW fixtures need int32)
    ar.read_uint16()  # dummy density

    if ar.loading_version < 12:
        ar.read_vec4()  # legacy attenuation
        ar.read_vec4()  # legacy spot params

    if ar.loading_version < 25:
        obj.object_key = ar.read_vstring()

    ar.read_int32()  # style
    ar.read_bool()  # triggered

    if ar.loading_version < 12:
        ar.read_string_binary()  # legacy projected texture

    ar.read_bool()  # use specularity
    obj.light_type = ar.read_int32()
    ar.read_color_ref()  # light color (unused DTO)

    if light_version >= 1:
        ar.read_float()  # multiplier / radius
        ar.read_float()  # falloff / angle

    ar.read_string_binary()  # projected texture

    if light_version < 7:
        ar.read_string_binary()  # corona texture

    if light_version >= 2:
        ar.read_uint32()  # visible mask

    flags = ar.read_int32()

    if flags & 1:
        _serialize_light_anim_intensity(ar)

    if flags & 2:
        _serialize_light_anim_color(ar)

    if ar.loading_version < 12:
        ar.read_object()  # legacy parent / owner (map sync)

    ar.read_color_ref()  # specular / ambient color (unused)

    if light_version < 7:
        ar.read_uint8()  # corona size / fade
        ar.read_uint8()  # corona flags

    ar.read_uint16()  # attenuation lookup / style index

    if light_version == 6:
        ar.read_uint16()  # corona scale (v6)
        ar.read_uint8()  # corona mode (v6)
        ar.read_float()  # corona distance (v6)

    if ar.loading_version < 11:
        ar.read_uint16()  # light bitmask low (legacy)
        ar.read_uint16()  # light bitmask high (legacy)
    else:
        ar.read_uint32()  # light bitmask
        ar.read_uint32()  # shadow / exclude mask

    ar.read_uint8()  # invisible

    if ar.loading_version >= 20:
        ar.read_int32()  # custom attenuation mode
        ar.read_float()  # custom attenuation param
        ar.read_string_binary()  # custom attenuation texture

    if light_version >= 3:
        # Static-geometry instance count only (pointers not streamed).
        ar.read_int32()  # linked SGI count

    if light_version >= 4:
        ar.read_uint32()  # influence / CullingFlags

    if light_version >= 5:
        ar.read_float()  # near clip
        ar.read_float()  # far clip / range

    if light_version >= 8:
        ar.read_bool()  # cast dynamic shadows


def serialize_shadow_map_spot(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VShadowMapComponentSpotDirectional::Serialize`` (loading)."""

    serialize_object_component_base(ar, obj)
    local_version = ar.read_uint8()

    if local_version > 0:
        ar.read_int32()  # Enabled

        if local_version >= 2:
            ar.read_int32()  # GeometryTypes

        ar.read_uint32()  # UseQuarterSizeShadowTexture
        ar.read_int32()  # ShadowMappingMode

        if local_version < 5:
            ar.read_int32()  # legacy quality / filter enum

        ar.read_int32()  # ShadowMapSize
        ar.read_float()  # SampleRadius

        if local_version >= 6:
            ar.read_float()  # SampleRadiusScaleWithDistance

        ar.read_int32()  # UseSurfaceSpecificShadowShaders

        if local_version < 5:
            ar.read_int32()  # legacy bias mode

        for _ in range(4):
            ar.read_float()  # Bias

        for _ in range(4):
            ar.read_float()  # SlopeScaled

        ar.read_uint32()  # FilterBitmask
        ar.read_float()  # NearClip
        ar.read_color_ref()  # shadow tint / fade color (unused)
        ar.read_float()  # ShadowBoxExtrudeMultiplier

        if local_version >= 3:
            ar.read_int32()  # FrontFacingShadows

    # SpotDirectional extras
    ar.read_uint32()  # CascadeCount

    if local_version >= 4:
        ar.read_int32()  # CascadeSelection

    for _ in range(4):
        ar.read_float()  # CascadeRange

    ar.read_int32()  # OverestimateCascades
    ar.read_float()  # CameraUpdateInterval
    ar.read_float()  # CameraUpdateAngle

    if local_version >= 4:
        ar.read_float()  # cascade blend / fade
        ar.read_float()  # cascade overlap


def serialize_base_entity(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VisBaseEntity_cl::Serialize`` — most entity fields unused by importer."""

    assert isinstance(obj, Object3D)
    serialize_object3d(ar, obj)

    entity_version = ar.read_uint8()
    ar.read_proxy_object()  # mesh / model resource (map sync)

    if entity_version >= 9:
        _serialize_visibility_data(ar)

    ar.read_vec3()  # bounding sphere center / size hint (unused)

    if ar.loading_version < 25:
        obj.object_key = ar.read_vstring()

    if entity_version < 9:
        ar.read_object()  # legacy visibility owner (map sync)

    ar.read_uint32()  # entity flags
    ar.read_uint32()  # render / light mask
    ar.read_bool()  # visible

    if entity_version < 9:
        ar.read_uint8()  # legacy LOD
        ar.read_int32()  # legacy status

    ar.read_int32()  # custom flags / category
    ar.read_object()  # linked light / child (map sync)

    if ar.read_int32() == 1:
        ar.read_bbox_vis()  # custom AABB (unused)

    if entity_version < 9:
        ar.read_vstring()  # legacy model path (unused)

    ar.read_bool()  # cast shadows

    if entity_version < 9:
        ar.read_float()  # legacy scale
        ar.read_uint32()  # legacy collision
        ar.read_bool()  # legacy lit
        ar.read_int32()  # legacy anim state

    ar.read_uint8()  # collision behavior
    ar.read_float()  # mass / density
    ar.read_uint32()  # physics flags
    ar.read_uint8()  # rigid-body type

    if entity_version < 9:
        ar.read(8)  # legacy physics padding
        ar.read_object()  # legacy physics body (map sync)

    ar.read_color_ref()  # tint / ambient
    ar.read_uint32()  # material override flags
    ar.read_uint32()  # shader flags
    ar.read_vec3()  # custom pivot / offset

    if entity_version >= 3:
        if entity_version < 8:
            if ar.read_bool():
                raise VArchiveError(
                    "inline VisSurfaceTextureSet not implemented")
        else:
            ar.read_proxy_object()  # surface texture set (map sync)

    if entity_version >= 4 and ar.read_uint8() != 0:
        for _ in range(ar.read_int32()):
            ar.read_uint32()  # bone / submesh visibility bitmask (unused)


def serialize_sector_box(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VSectorBox`` — GamePlugin entity; archive uses ``VisBaseEntity_cl``."""

    serialize_base_entity(ar, obj)


def serialize_electronic_display(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VElectronicDisplay_cl::Serialize`` (loading)."""

    serialize_base_entity(ar, obj)
    version = ar.read_int8()
    ar.read_int32()  # display flags
    ar.read_int32()  # display flags

    if version >= 2:
        ar.read_int32()  # extra flags

    ar.read_string_binary()  # movie / texture path
    ar.read_string_binary()  # movie / texture path


def serialize_particle_constraint(
        ar: VArchiveReader,
        obj: ArchiveObject) -> int:
    """``VisParticleConstraint_cl::Serialize`` (loading)."""

    assert isinstance(obj, Object3D)
    serialize_object3d(ar, obj)
    version = ar.read_int8()
    ar.read_color_ref()  # debug / influence color
    ar.read_int32()  # reflect behavior
    ar.read_bool()  # enabled
    ar.read_bool()  # debug render
    ar.read_float()  # restitution
    ar.read_uint32()  # influence mask

    if version >= 2:
        ar.read_float()  # extra radius / padding

    return version


def serialize_particle_constraint_obox(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisParticleConstraintAABox_cl`` / ``OBox`` share this Serialize."""

    serialize_particle_constraint(ar, obj)
    ar.read_bbox_vis()
    ar.read_bool()  # inverted / inside


def serialize_particle_constraint_point(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:

    serialize_particle_constraint(ar, obj)
    ar.read_float()  # radius


def serialize_particle_constraint_sphere(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:

    serialize_particle_constraint(ar, obj)
    ar.read_float()  # radius
    ar.read_bool()  # inverted
    ar.read_int32()  # axis / flags


def serialize_particle_constraint_plane(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:

    version = serialize_particle_constraint(ar, obj)

    for _ in range(4):
        ar.read_float()  # hkvPlane SerializeX

    if ar.loading_version >= 22:
        ar.read_bool()
        ar.read_float()
        ar.read_float()

        if version >= 3:
            ar.read_float()


def serialize_particle_constraint_cambox(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:

    serialize_particle_constraint(ar, obj)
    ar.read_vis_vector()  # box extent


def serialize_particle_constraint_terrain(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:

    serialize_particle_constraint(ar, obj)
    ar.read_int8()  # local version
    ar.read_object()  # VTerrain


def serialize_particle_affector_fan(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisParticleAffectorFan_cl`` / ``Cyclone`` share this Serialize."""

    serialize_particle_constraint(ar, obj)
    ar.read_float()  # intensity
    ar.read_float()  # radius
    ar.read_float()  # angle / falloff


def serialize_particle_affector_gravity(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:

    serialize_particle_constraint(ar, obj)
    ar.read_float()  # intensity
    ar.read_float()  # radius


def _serialize_particle_constraint_list(ar: VArchiveReader) -> None:
    """``VisParticleConstraintList_cl::SerializeX`` (loading)."""

    for _ in range(ar.read_int32()):
        ar.read_object()  # constraint (map sync)
        ar.read_int32()  # influence flags


def _serialize_particle_group(ar: VArchiveReader) -> None:
    """``ParticleGroupBase_cl::SerializeX`` (loading)."""

    dummy = Object3D("ParticleGroupBase_cl")
    serialize_object3d(ar, dummy)
    version = ar.read_int32()
    ar.read_float()  # time scale / lifetime

    if version >= 2:
        ar.read_color_ref()  # tint

    if version >= 3:
        ar.read_uint32()  # visible bitmask

    if version >= 4:
        ar.read_vis_vector()  # wind / offset

    if version >= 5:
        ar.read_bool()  # paused / finished

    if version >= 6:
        ar.read_bool()  # extra flag

    if version >= 7:
        ar.read_object()  # attach entity

    _serialize_particle_constraint_list(ar)


def serialize_particle_effect(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VisParticleEffect_cl::Serialize`` (loading)."""

    assert isinstance(obj, Object3D)
    serialize_object3d(ar, obj)
    version = ar.read_int32()
    file_mode = ar.read_uint8() if version >= 1 else 0

    if version >= 4:
        ar.read_uint32()  # random seed / flags

    if file_mode == 0:
        ar.read_string_binary()  # .vparticle path
    elif file_mode == 1:
        ar.read_object()  # VisParticleEffectFile_cl

    if version >= 1 and ar.loading_version < 25:
        ar.read_vstring()  # object key (legacy)

    if version >= 3:
        ar.read_bool()  # playing
        ar.read_bool()  # finished / looped

    for _ in range(ar.read_int32()):
        present = True if version < 2 else ar.read_bool()

        if present:
            _serialize_particle_group(ar)


def serialize_camera_position_entity(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``CameraPositionEntity::Serialize`` — camera extras unused by importer."""

    serialize_base_entity(ar, obj)
    ar.read_uint8()  # camera local version / flags
    ar.read_float()  # FOV
    ar.read_float()  # near clip
    ar.read_float()  # far clip


def serialize_sun_glare(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VSunGlare::Serialize`` (loading) — Object3D plus glare params."""

    assert isinstance(obj, Object3D)
    serialize_object3d(ar, obj)

    version = ar.read_uint8()
    ar.read_uint32()  # flags / mask
    ar.read_color_ref()  # tint
    ar.read_int32()  # quality / samples
    ar.read_float()  # intensity / size
    ar.read_bool()  # enabled

    if version >= 1:
        ar.read_float()  # bloom / fade


def serialize_simple_animation_component(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VSimpleAnimationComponent::Serialize`` (loading)."""

    serialize_object_component_base(ar, obj)
    version = ar.read_uint8()
    ar.read_vstring()  # animation / sequence name (unused)

    if version >= 1:
        ar.read_int32()  # flags / loop mode


def serialize_skeleton_serialization_proxy(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VSkeletonSerializationProxy::Serialize`` (loading)."""

    ctype = ar.read_uint8()

    if ctype == 1:
        ar.read_proxy_object()  # owner mesh
    elif ctype == 2:
        ar.read_proxy_object()  # owner animation
        ar.read_int32()  # owner index


def serialize_vertex_deformer_stack(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisVertexDeformerStack_cl::Serialize`` (loading)."""

    serialize_typed_engine_object(ar, obj)

    for _ in range(ar.read_int32()):
        ar.read_object()  # deformer entry (map sync)


def serialize_skinning_deformer(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisSkinningDeformer_cl::Serialize`` (loading)."""

    serialize_typed_engine_object(ar, obj)
    ar.read_bool()  # hardware / mode flag


def _serialize_anim_event_list(ar: VArchiveReader) -> None:
    """``VisAnimEventList_cl::SerializeX`` (loading)."""

    ar.read_float()  # start / cursor
    ar.read_float()  # end time
    ar.read_bool()  # direction
    count = ar.read_int32()

    for _ in range(count):
        ar.read_float()  # event time

        if ar.read_bool():
            ar.read_string_binary()  # event key
        else:
            ar.read_int32()  # event id

        if ar.loading_version >= 24:
            ar.read_bool()  # auto-remove

    ar.read_int32()  # current event
    ar.read_int32()  # current loop


def _serialize_anim_control_x(ar: VArchiveReader) -> None:
    """``VisAnimControl_cl::SerializeX`` (loading)."""

    ar.read_proxy_object()  # anim sequence
    ar.read_float()  # current sequence time
    ar.read_bool()  # paused
    ar.read_uint32()  # flags
    ar.read_float()  # speed factor
    ar.read_float()  # start anim time
    _serialize_anim_event_list(ar)

    for _ in range(ar.read_int32()):
        ar.read_object()  # event listener

    for _ in range(ar.read_int32()):
        _serialize_anim_control_x(ar)  # synchronized control (inline)


def serialize_anim_final_skeletal_result(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisAnimFinalSkeletalResult_cl::Serialize`` (loading)."""

    serialize_typed_engine_object(ar, obj)
    ar.read_proxy_object()  # skeleton
    ar.read_object()  # skeletal anim control (map sync)


def serialize_skeletal_anim_control(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VisSkeletalAnimControl_cl::Serialize`` (loading)."""

    # IVisAnimResultGenerator_cl::Serialize
    serialize_typed_engine_object(ar, obj)
    ar.read_proxy_object()  # skeleton
    # VisAnimControl_cl::SerializeX on the control subobject
    _serialize_anim_control_x(ar)


def serialize_anim_config(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VisAnimConfig_cl::Serialize`` (loading)."""

    serialize_typed_engine_object(ar, obj)
    ar.read_proxy_object()  # dynamic mesh
    # High-bit version markers (0x8000000x) must be compared as unsigned.
    iversion = ar.read_uint32()

    if iversion >= 0x80000000:
        if iversion >= 0x80000001:
            ar.read_proxy_object()  # skeleton

        ar.read_int32()  # final-result placeholder
        ar.read_int32()  # skin mode
        ar.read_bool()  # parent-zone flag
        ar.read_int32()  # parent-zone extras

    ar.read_object()  # vertex deformer stack
    ar.read_object()  # final skeletal result
    ar.read_bool()  # modified bbox flag

    if iversion >= 0x80000002:
        ar.read_bool()  # mesh flag


def serialize_sequence_set_proxy(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VSequenceSetSerializationProxy::Serialize`` (loading)."""

    ar.read_string_binary()  # animation set path (unused)


def serialize_sequence_proxy(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VSequenceSerializationProxy::Serialize`` (loading)."""

    ar.read_uint8()  # anim type
    ar.read_proxy_object()  # sequence set
    ar.read_string_binary()  # sequence name (unused)


def serialize_model_serialization_proxy(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VModelSerializationProxy::Serialize`` (loading)."""

    # VTypedObject::Serialize is a no-op on load for this proxy.
    ar.read_string_binary()  # dynamic mesh path (unused)

    for _ in range(ar.read_int32()):
        ar.read_proxy_object()  # VisAnimSequenceSet proxy (map sync)


def serialize_static_mesh_alpha_controller(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VStaticMeshAlphaController::Serialize`` (loading)."""

    ar.read_float()  # alpha / fade


def _serialize_texture_exchange(ar: VArchiveReader) -> None:
    """``VTextureObject::DoArchiveExchange`` (loading)."""

    if ar.read_bool():
        ar.read_uint16()  # load flags
        ar.read_string_binary()  # filename


def _serialize_surface_textures(ar: VArchiveReader) -> None:
    """``VisSurfaceTextures_cl::SerializeX`` (loading)."""

    ar.read_uint8()  # local version
    ar.read_vec4()  # lightmap scale / offset
    _serialize_texture_exchange(ar)  # diffuse
    _serialize_texture_exchange(ar)  # normal
    _serialize_texture_exchange(ar)  # specular

    for _ in range(4):
        _serialize_texture_exchange(ar)  # model lightmaps

    for _ in range(ar.read_int16()):
        _serialize_texture_exchange(ar)  # auxiliary


def _serialize_surface(ar: VArchiveReader) -> None:
    """``VisSurface_cl::SerializeX`` (loading)."""

    _serialize_surface_textures(ar)
    version = ar.read_uint8()
    ar.read_vstring()  # name
    ar.read_int32()  # material flags
    ar.read_color_ref()  # ambient
    ar.read_uint8()  # transparency
    ar.read_uint8()  # sorting key
    ar.read_uint8()  # lighting method
    ar.read_uint8()  # deferred ID
    ar.read_bool()  # cast static shadows

    if version < 1:
        ar.read_bool()  # legacy manipulations
    else:
        ar.read_uint8()  # pass type

    ar.read_bool()  # double sided
    ar.read_bool()  # depth write
    ar.read_float()  # spec mul
    ar.read_float()  # spec exp
    ar.read_float()  # parallax scale
    ar.read_float()  # parallax bias
    ar.read_float()  # alpha threshold
    ar.read_float()  # depth bias
    ar.read_float()  # depth bias clamp
    ar.read_float()  # slope scaled depth bias
    ar.read_int32()  # user flags
    ar.read_vstring()  # user data
    ar.read_uint8()  # shader mode
    _serialize_effect_config(ar)

    if version >= 2:
        ar.read_uint8()  # mobile shader flags


def serialize_volumetric_cone(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VolumetricCone_cl::Serialize`` (loading)."""

    assert isinstance(obj, Object3D)
    serialize_object3d(ar, obj)
    version = ar.read_int32()
    ar.read_color_ref()  # tint

    for _ in range(5):
        ar.read_float()  # radius / length / angles

    ar.read_object()  # linked light
    ar.read_uint8()  # enabled
    ar.read_uint8()  # flags
    ar.read_uint8()  # flags
    ar.read_float()  # intensity / fade

    if version >= 1:
        ar.read_uint32()  # light mask

    if version >= 2:
        ar.read_float()  # extra param
        ar.read_float()  # extra param


def serialize_surface_texture_set_proxy(
    ar: VArchiveReader,
    obj: ArchiveObject,
) -> None:
    """``VSurfaceTextureSetSerializationProxy::Serialize`` (loading)."""

    version = ar.read_uint8()
    count = ar.read_int16()
    as_surfaces = ar.read_bool() if version >= 1 else False

    for _ in range(count):
        if as_surfaces:
            _serialize_surface(ar)
        else:
            _serialize_surface_textures(ar)


def serialize_projected_wallmark(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:
    """``VProjectedWallmark::Serialize`` (loading)."""

    version = ar.read_int32()
    ar.read_vis_vector()  # origin
    ar.read_vis_vector()  # direction
    ar.read_vis_vector()  # up
    ar.read_vis_vector()  # right
    ar.read_vis_vector()  # extent / size
    ar.read_float()  # radius / fade
    ar.read_string_binary()  # texture path (unused)
    ar.read_color_ref()  # tint
    ar.read_uint32()  # flags / mask
    ar.read_float()  # intensity
    ar.read_float()  # rotation

    if version >= 1:
        ar.read_uint32()  # extra flags

    if version >= 2:
        ar.read_bool()  # enabled / affect static

    if 3 <= version <= 7:
        ar.read_int64()  # unique id (unused)

    if version >= 4:
        ar.read_float()  # depth / bias

    if version >= 5:
        ar.read_float()  # far / lifetime

    if version >= 6:
        ar.read_uint32()  # sorting / stencil

    if version >= 7:
        _serialize_effect_config(ar)

    if version >= 9:
        ar.read_int32()  # visibility level


def serialize_time_of_day(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """Minimal ``VTimeOfDay`` walk — leaf-skip preferred when lengths exist."""

    raise VArchiveError("VTimeOfDay should be leaf-skipped or fully ported")


def serialize_time_of_day_component(
        ar: VArchiveReader,
        obj: ArchiveObject) -> None:

    serialize_object_component_base(ar, obj)


def serialize_corona_component(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VCoronaComponent::Serialize`` (loading)."""

    serialize_object_component_base(ar, obj)
    version = ar.read_int8()
    ar.read_string_binary()  # corona texture
    ar.read_float()  # size / scale
    ar.read_uint32()  # color / flags
    ar.read_uint32()  # color / flags
    ar.read_float()  # fade / distance
    ar.read_float()  # fade / distance
    ar.read_float()  # fade / distance
    ar.read_uint8()  # flags
    ar.read_uint8()  # flags
    ar.read_int32()  # sort / mask

    if version >= 1:
        ar.read_uint32()  # extra mask

    if version >= 2:
        ar.read_int32()  # extra param
