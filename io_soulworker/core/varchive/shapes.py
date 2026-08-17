from __future__ import annotations

from dataclasses import dataclass, field

from io_soulworker.core.varchive.objects import (
    ArchiveObject,
    LightSource,
    Object3D,
    StaticMeshInstance,
)
from io_soulworker.core.varchive.reader import VArchiveReader
from io_soulworker.core.varchive.registry import (
    ALIASES,
    LEAF_SKIP_CLASSES,
    build_serializers,
)


@dataclass
class ShapesArchiveResult:
    """Parsed SHPS object stream (after the statistics header)."""

    objects: list[ArchiveObject] = field(default_factory=list)
    static_meshes: list[StaticMeshInstance] = field(default_factory=list)
    entities: list[Object3D] = field(default_factory=list)
    lights: list[LightSource] = field(default_factory=list)
    visibility_zones: list[ArchiveObject] = field(default_factory=list)
    think_interval: float = 0.0
    skipped_classes: dict[str, int] = field(default_factory=dict)
    zone_version: int = 0
    zone_pivot: tuple[float, float, float] = (0.0, 0.0, 0.0)


def _collect_shapes(ar: VArchiveReader, result: ShapesArchiveResult) -> None:

    result.objects = list(ar.objects)
    result.skipped_classes = dict(ar.skipped_classes)

    for obj in ar.objects:
        if isinstance(obj, StaticMeshInstance):
            result.static_meshes.append(obj)
        elif isinstance(obj, LightSource):
            result.lights.append(obj)
        elif isinstance(obj, Object3D):
            result.entities.append(obj)


def read_shapes_payload(
    data: bytes | memoryview,
    *,
    archive_version: int,
    scene_version: int,
) -> ShapesArchiveResult:
    """Walk a SHPS object stream the way ``VSceneLoader::ReadShapeChunk`` does."""

    use_object_lengths = scene_version >= 13
    has_per_object_range = scene_version >= 9

    ar = VArchiveReader(
        data,
        loading_version=archive_version,
        use_object_lengths=use_object_lengths,
        has_per_object_range=has_per_object_range,
        serializers=build_serializers(),
        aliases=ALIASES,
        leaf_skip_classes=set(LEAF_SKIP_CLASSES),
    )

    result = ShapesArchiveResult()

    if scene_version >= 6:
        zone_count = ar.read_int32()

        for _ in range(zone_count):
            zone = ar.read_object()

            if zone is not None:
                result.visibility_zones.append(zone)

    if scene_version >= 5:
        # Prefix objects land in ``ar.objects``; not re-listed here.
        ar.read_object()  # scene script (unused DTO)

        if scene_version >= 14:
            result.think_interval = ar.read_float()

        ar.read_object()  # sky (unused DTO; still in ar.objects)

    if scene_version >= 10:
        ar.read_object()  # renderer (unused DTO; still in ar.objects)
        ar.read_object()  # time of day (unused DTO; still in ar.objects)

    while not ar.eof():
        # Free scene objects — classified into result lists after the walk.
        ar.read_object()

    _collect_shapes(ar, result)
    return result


def read_zone_file(data: bytes | memoryview) -> ShapesArchiveResult:
    """Walk a ``.vzone`` stream (``VZoneShapesArchive``).

    Header: archive version, zone local version, optional ``hkvVec3d`` pivot
    (local >= 10), then object / non-null / root counts. No SHPS type
    statistics and no per-object progress prefix.
    """

    ar = VArchiveReader(
        data,
        loading_version=30,
        use_object_lengths=False,
        has_per_object_range=False,
        serializers=build_serializers(),
        aliases=ALIASES,
        leaf_skip_classes=set(),
        zone_file=True,
    )

    result = ShapesArchiveResult()
    archive_version = ar.read_int32()
    ar.loading_version = archive_version
    result.zone_version = ar.read_int32()

    if result.zone_version >= 10:
        result.zone_pivot = (
            ar.read_double(),
            ar.read_double(),
            ar.read_double())

    ar.read_int32()  # object count
    ar.read_int32()  # non-null count
    root_count = ar.read_int32()
    ar.read_int32()  # reserved

    for _ in range(root_count):
        if ar.eof():
            break

        ar.read_object()

    _collect_shapes(ar, result)
    return result
