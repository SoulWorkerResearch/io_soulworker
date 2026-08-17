from __future__ import annotations

from dataclasses import dataclass, field
from logging import error, info, warning
from pathlib import Path

from bpy.types import Collection, Context, Object

from io_soulworker.core.varchive.objects import StaticMeshInstance
from io_soulworker.core.varchive.shapes import read_zone_file
from io_soulworker.file_import.collections import (
    collection_segments_under_resources,
    ensure_collection_hierarchy,
    find_or_create_child_collection,
    leaf_collection_color_tag,
    set_active_collection,
)
from io_soulworker.file_import.model.file_reader import ModelFileReader
from io_soulworker.file_import.resource_path import resolve_resource_path
from io_soulworker.file_import.scene.file_reader import SceneFileReader
from io_soulworker.unit_scale import vision_matrix_to_blender


def _blender_id_int32(value: int) -> int:
    """Pack a uint32 bit mask into a Blender ID property (signed int32)."""

    value &= 0xFFFFFFFF

    return value - 0x100000000 if value >= 0x80000000 else value


def apply_collision_only_visibility(obj: Object) -> None:
    """Draw ``m_iVisibleMask == 0`` helpers as bounds; skip shading and render."""

    obj.display_type = "BOUNDS"
    obj.display.show_shadows = False
    obj.hide_render = True
    obj.hide_probe_volume = True
    obj.hide_probe_sphere = True
    obj.hide_probe_plane = True
    obj.visible_camera = False
    obj.visible_diffuse = False
    obj.visible_glossy = False
    obj.visible_transmission = False
    obj.visible_volume_scatter = False
    obj.visible_shadow = False


def scene_data_directory(scene_path: Path) -> Path:
    """Sidecar folder ``{name}.vscene_data`` next to a ``.vscene``."""

    return scene_path.with_suffix(scene_path.suffix + "_data")


def zone_files_for_scene(scene_path: Path) -> list[Path]:

    data_dir = scene_data_directory(scene_path)

    if not data_dir.is_dir():
        return []

    return sorted(
        path for path in data_dir.glob("*.vzone") if path.is_file()
    )


@dataclass
class SceneImportResult:
    """Outcome of placing SHPS / zone static meshes into the Blender scene."""

    collection: Collection | None = None
    objects: list[Object] = field(default_factory=list)
    missing_paths: list[str] = field(default_factory=list)
    static_mesh_count: int = 0
    zone_mesh_count: int = 0


class SceneImporter:
    """Parse a ``.vscene`` (and its ``.vzone`` sidecars) into Zones collections."""

    def __init__(
        self,
        path: Path,
        context: Context,
        resources_root: str | Path,
        *,
        emission_strength: float = 7.0,
    ) -> None:

        self.path = Path(path)
        self.context = context
        self.resources_root = Path(resources_root)
        self.emission_strength = emission_strength

    def run(self) -> SceneImportResult:

        result = SceneImportResult()

        if not self.resources_root.is_dir():
            raise FileNotFoundError(
                f"Resources root is not a directory: {self.resources_root}"
            )

        reader = SceneFileReader(self.path)
        reader.run()

        zones = self._prepare_zones_collection()
        result.collection = zones
        root = find_or_create_child_collection(zones, "Root")
        set_active_collection(self.context, root)

        if reader.shapes is None:
            warning("Scene has no SHPS chunk: %s", self.path)
        else:
            result.static_mesh_count = self._place_instances(
                reader.shapes.static_meshes,
                root,
                result,
            )
            info(
                "Imported %d static mesh instance(s) into Zones/Root from %s",
                result.static_mesh_count,
                self.path.name,
            )

        for zone_path in zone_files_for_scene(self.path):
            zone_collection = find_or_create_child_collection(
                zones,
                zone_path.stem,
            )
            zone_collection.color_tag = "COLOR_05"

            try:
                parsed = read_zone_file(zone_path.read_bytes())
            except Exception as exc:
                error("Failed to parse zone %s: %s", zone_path.name, exc)
                continue

            placed = self._place_instances(
                parsed.static_meshes,
                zone_collection,
                result,
            )
            result.zone_mesh_count += placed
            info(
                "Imported %d static mesh instance(s) into Zones/%s",
                placed,
                zone_path.stem,
            )

        if result.missing_paths:
            warning(
                "Scene import skipped %d missing mesh path(s)",
                len(result.missing_paths),
            )

        return result

    def _place_instances(
        self,
        instances: list[StaticMeshInstance],
        collection: Collection,
        result: SceneImportResult,
    ) -> int:

        placed = 0

        for instance in instances:
            resolved = resolve_resource_path(
                self.resources_root,
                instance.path,
            )

            if resolved is None:
                error("Missing static mesh: %s", instance.path)
                result.missing_paths.append(instance.path)
                continue

            object_name = Path(
                instance.path.replace("\\", "/")
            ).stem

            matrix = vision_matrix_to_blender(instance.matrix)

            obj = ModelFileReader(
                resolved,
                self.context,
                self.emission_strength,
                collection=collection,
                matrix_world=matrix,
                object_name=object_name,
                reuse_mesh=True,
            ).run()

            obj["soulworker_class"] = instance.class_name
            obj["soulworker_path"] = instance.path
            obj["soulworker_collision_behavior"] = instance.collision_behavior
            obj["soulworker_physics_hint"] = instance.physics_hint
            obj["soulworker_visible_mask"] = _blender_id_int32(
                instance.visible_mask
            )
            obj["soulworker_collision_only"] = instance.is_collision_only

            if instance.is_collision_only:
                apply_collision_only_visibility(obj)

            result.objects.append(obj)
            placed += 1

        return placed

    def _prepare_zones_collection(self) -> Collection:

        segments = collection_segments_under_resources(
            str(self.resources_root),
            self.path,
        )

        if segments is None:
            segments = ["project", "Scenes", self.path.stem]

        scene_root = ensure_collection_hierarchy(self.context, segments)
        scene_root.color_tag = leaf_collection_color_tag(self.path)

        zones = find_or_create_child_collection(scene_root, "Zones")
        zones.color_tag = "COLOR_04"

        return zones
