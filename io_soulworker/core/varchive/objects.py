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

    def __init__(self, class_name: str = "VisObject3D_cl") -> None:

        super().__init__(class_name)
        self.position = Vector((0.0, 0.0, 0.0))
        self.orientation = Vector((0.0, 0.0, 0.0))


class LightSource(Object3D):
    """VisLightSource_cl placement + intensity."""

    intensity = 0.0
    light_type = 0

    def __init__(self) -> None:

        super().__init__("VisLightSource_cl")
        self.intensity = 0.0
        self.light_type = 0
