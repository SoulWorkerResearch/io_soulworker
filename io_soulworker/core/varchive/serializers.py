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


def serialize_typed_engine_object(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VisTypedEngineObject_cl::Serialize`` (loading, archive >= 28)."""

    if ar.loading_version < 28:
        return

    local_version = ar.read_uint8()

    if local_version >= 1:
        serialize_components(ar, obj)

    if local_version >= 2:
        obj.unique_id = ar.read_int64()


def serialize_object_component_base(ar: VArchiveReader, obj: ArchiveObject) -> None:
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


def _serialize_visibility_data(ar: VArchiveReader) -> None:
    """``VVisibilityData::Serialize_VisData`` — fields unused by importer."""

    ar.read_uint8()  # vis-data version
    ar.read_bbox_x()  # bounding box
    ar.read_vec3()  # frustum hint / center
    ar.read_uint32()  # visibility flags
    ar.read_float()  # near clip / radius-related
    ar.read_int32()  # visibility bitmask / zone flags
    ar.read_float()  # far / fade


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


def serialize_forward_rendering_system(ar: VArchiveReader, obj: ArchiveObject) -> None:
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


def serialize_fake_glow_post_process(ar: VArchiveReader, obj: ArchiveObject) -> None:

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


def serialize_copy_post_process(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``VSimpleCopyPostprocess`` / ``VCopyPostProcess`` wire (loading).

    LoginBackground names the class ``VCopyPostProcess``; the stock plugin
    type is ``VSimpleCopyPostprocess``. Both write active + renderer ref.
    """

    ar.read_bool()  # active
    ar.read_object()  # renderer


def serialize_static_geometry_instance(ar: VArchiveReader) -> None:
    """``VisStaticGeometryInstance_cl::SerializeX`` (loading) — unused DTO."""

    version = ar.read_uint8()

    if version < 8:
        ar.read_float()  # legacy far clip / LOD

        if version >= 4:
            ar.read_float()  # legacy near / fade
            ar.read_vec3()  # legacy center
            ar.read_int32()  # legacy vis flags
    else:
        _serialize_visibility_data(ar)

    ar.read_int32()  # geometry type

    if version < 8:
        ar.read_bbox_vis()  # local AABB (unused)

    ar.read_uint32()  # light mask

    # Stock Vision also writes trace mask here. CharacterSelect / login
    # fixtures (SGI v8) omit those 4 bytes — validated via object-length
    # checksum against the parent SMI payload.
    if version < 8:
        ar.read_uint32()  # trace mask
        ar.read_uint32()  # visible (legacy)
    # version >= 8: no separate trace mask on disk for SW KR fixtures

    ar.read_bool()  # cast / receive shadows
    ar.read_int32()  # collision / physics flags

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


def serialize_static_mesh_instance(ar: VArchiveReader, obj: ArchiveObject) -> None:
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
        ar.read_int32()  # visibility level

    if obj.version >= 1:
        if obj.version < 5:
            ar.read_uint16()  # light / render bitmask (legacy)
        else:
            ar.read_uint32()  # light / render bitmask

    if obj.version >= 9:
        ar.read_uint8()  # collision behavior

    # Physics hint appears with iVersion >= 10 (current write path).
    if obj.version >= 10:
        ar.read_uint8()  # physics hint

    for _ in range(ar.read_int32()):
        serialize_static_geometry_instance(ar)

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


def serialize_camera_position_entity(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """``CameraPositionEntity::Serialize`` — camera extras unused by importer."""

    serialize_base_entity(ar, obj)
    ar.read_uint8()  # camera local version / flags
    ar.read_float()  # FOV
    ar.read_float()  # near clip
    ar.read_float()  # far clip


def serialize_time_of_day(ar: VArchiveReader, obj: ArchiveObject) -> None:
    """Minimal ``VTimeOfDay`` walk — leaf-skip preferred when lengths exist."""

    raise VArchiveError("VTimeOfDay should be leaf-skipped or fully ported")


def serialize_time_of_day_component(ar: VArchiveReader, obj: ArchiveObject) -> None:

    serialize_object_component_base(ar, obj)


def serialize_corona_component(ar: VArchiveReader, obj: ArchiveObject) -> None:

    serialize_object_component_base(ar, obj)
