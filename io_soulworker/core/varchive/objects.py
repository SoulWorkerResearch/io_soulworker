from __future__ import annotations

from mathutils import Matrix, Vector


class ArchiveObject:
    """Base DTO produced by VArchive::ReadObject."""

    class_name = ""
    archive_index = -1
    unique_id = 0
    object_key = ""

    def __init__(self, class_name: str = "") -> None:

        self.class_name = class_name
        self.archive_index = -1
        self.unique_id = 0
        self.object_key = ""
        self.components: list[ArchiveObject] = []


class StaticMeshInstance(ArchiveObject):
    """VisStaticMeshInstance_cl fields needed for import."""

    path = ""
    matrix = Matrix.Identity(4)
    version = 0
    collision_behavior = 0
    physics_hint = 0
    visibility_level = 0
    light_mask = 0
    geometries: list[dict] = []

    def __init__(self) -> None:

        super().__init__("VisStaticMeshInstance_cl")
        self.path = ""
        self.matrix = Matrix.Identity(4)
        self.version = 0
        self.collision_behavior = 0
        self.physics_hint = 0
        self.visibility_level = 0
        self.light_mask = 0
        self.geometries = []

    @property
    def translation(self) -> Vector:

        return Vector((
            self.matrix[0][3],
            self.matrix[1][3],
            self.matrix[2][3],
        ))

    @property
    def visible_mask(self) -> int:
        """OR of SGI ``m_iVisibleMask`` values (0 = not rendered)."""

        if not self.geometries:
            return 0

        mask = 0

        for geometry in self.geometries:
            mask |= int(geometry.get("visible_mask", 0))

        return mask

    @property
    def is_collision_only(self) -> bool:
        """True when every SGI has a zero visible mask (helper collision mesh)."""

        return bool(self.geometries) and self.visible_mask == 0


class Object3D(ArchiveObject):
    """VisObject3D_cl / entity placement."""

    position = Vector((0.0, 0.0, 0.0))
    orientation = Vector((0.0, 0.0, 0.0))
    rotation_matrix: Matrix | None = None
    model_path = ""
    preferred_animation = ""
    animation_set_paths: list[str] = []

    def __init__(self, class_name: str = "VisObject3D_cl") -> None:

        super().__init__(class_name)
        self.position = Vector((0.0, 0.0, 0.0))
        self.orientation = Vector((0.0, 0.0, 0.0))
        self.rotation_matrix = None
        self.model_path = ""
        self.preferred_animation = ""
        self.animation_set_paths = []


class ModelSerializationProxy(ArchiveObject):
    """``VModelSerializationProxy`` — dynamic mesh path + sequence sets."""

    path = ""
    sequence_set_paths: list[str] = []

    def __init__(self) -> None:

        super().__init__("VModelSerializationProxy")
        self.path = ""
        self.sequence_set_paths = []


class SequenceSetSerializationProxy(ArchiveObject):
    """``VSequenceSetSerializationProxy`` — ``.anim`` resource path."""

    path = ""

    def __init__(self) -> None:

        super().__init__("VSequenceSetSerializationProxy")
        self.path = ""


class SimpleAnimationComponent(ArchiveObject):
    """``VSimpleAnimationComponent`` — preferred sequence name."""

    animation_name = ""

    def __init__(self) -> None:

        super().__init__("VSimpleAnimationComponent")
        self.animation_name = ""


class LightSource(Object3D):
    """``VisLightSource_cl`` placement and the light fields identified so far.

    Every field below was matched against the vForge ``DynLightShape``
    properties of the scenes' static lighting files (same position, same
    value) before it was named. Distances are Vision units (centimetres).
    ``flags`` and ``cast_shadows`` are raw: no vForge property confirmed what
    they mean.
    """

    TYPE_POINT = 1
    TYPE_DIRECTIONAL = 3
    TYPE_SPOTLIGHT = 5

    light_type = 0
    """Point, directional or spotlight (``TYPE_*``)."""

    radius = 0.0
    """Reach of the light (vForge ``Radius``)."""

    multiplier = 1.0
    """Brightness factor with no unit (vForge ``Multiplier``)."""

    color = 0xFFFFFFFF
    """Bytes r, g, b, a read as one little-endian uint32 (vForge ``LightColor``)."""

    spot_angle = 0.0
    """Full cone angle in degrees (vForge ``SpotAngle``); only spotlights use it."""

    fade_start = 0.0
    """vForge ``DistanceFadeStart``."""

    fade_end = 0.0
    """vForge ``DistanceFadeEnd``."""

    projected_texture = ""
    attenuation_texture = ""
    visible_mask = 0xFFFFFFFF
    """vForge ``VisibleBitmask``; zero means no render context shows the light."""

    world_influence_mask = 0
    """vForge ``WorldInfluenceMask``."""

    object_influence_mask = 0
    """vForge ``ObjectInfluenceMask``."""

    flags = 0
    cast_shadows = False

    def __init__(self) -> None:

        super().__init__("VisLightSource_cl")
        self.light_type = 0
        self.radius = 0.0
        self.multiplier = 1.0
        self.color = 0xFFFFFFFF
        self.spot_angle = 0.0
        self.fade_start = 0.0
        self.fade_end = 0.0
        self.projected_texture = ""
        self.attenuation_texture = ""
        self.visible_mask = 0xFFFFFFFF
        self.world_influence_mask = 0
        self.object_influence_mask = 0
        self.flags = 0
        self.cast_shadows = False

    @property
    def rgb(self) -> tuple[int, int, int]:
        """The colour as 0-255 red, green and blue bytes."""

        return (
            self.color & 0xFF,
            (self.color >> 8) & 0xFF,
            (self.color >> 16) & 0xFF,
        )
