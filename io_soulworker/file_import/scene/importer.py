from __future__ import annotations

from dataclasses import dataclass, field
from logging import error, info, warning
from pathlib import Path

import bpy
from bpy.types import ArmatureModifier, Collection, Context, Object
from mathutils import Euler, Matrix

from io_soulworker.core.varchive.objects import Object3D, StaticMeshInstance
from io_soulworker.core.varchive.shapes import read_zone_file
from io_soulworker.file_import.animation.file_reader import (
    AnimationFileReader,
    AnimationImportSource,
)
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
from io_soulworker.unit_scale import vision_matrix_to_blender, vision_to_blender


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


def entity_world_matrix(entity: Object3D) -> Matrix:
    """Vision entity position + XYZ euler (radians) → Blender world matrix."""

    translation = Matrix.Translation(vision_to_blender(entity.position))
    rotation = Euler(entity.orientation, "XYZ").to_matrix().to_4x4()

    return translation @ rotation


@dataclass
class SceneImportResult:
    """Outcome of placing SHPS / zone static meshes into the Blender scene."""

    collection: Collection | None = None
    objects: list[Object] = field(default_factory=list)
    missing_paths: list[str] = field(default_factory=list)
    static_mesh_count: int = 0
    zone_mesh_count: int = 0
    entity_count: int = 0


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
            result.entity_count += self._place_entities(
                reader.shapes.entities,
                root,
                result,
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
            result.entity_count += self._place_entities(
                parsed.entities,
                zone_collection,
                result,
            )

        if result.missing_paths:
            warning(
                "Scene import skipped %d missing mesh path(s)",
                len(result.missing_paths),
            )

        info(
            "Imported %d entity mesh(es) with model paths from %s",
            result.entity_count,
            self.path.name,
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

    def _place_entities(
        self,
        entities: list[Object3D],
        parent: Collection,
        result: SceneImportResult,
    ) -> int:

        placed = 0
        collection: Collection | None = None

        for entity in entities:
            if not entity.model_path:
                continue

            if collection is None:
                collection = find_or_create_child_collection(parent, "Entities")
                collection.color_tag = "COLOR_06"

            resolved = resolve_resource_path(
                self.resources_root,
                entity.model_path,
            )

            if resolved is None:
                error("Missing entity model: %s", entity.model_path)
                result.missing_paths.append(entity.model_path)
                continue

            object_name = Path(
                entity.model_path.replace("\\", "/")
            ).stem

            obj = ModelFileReader(
                resolved,
                self.context,
                self.emission_strength,
                collection=collection,
                matrix_world=entity_world_matrix(entity),
                object_name=object_name,
                reuse_mesh=False,
            ).run()

            obj["soulworker_class"] = entity.class_name
            obj["soulworker_path"] = entity.model_path
            obj["soulworker_preferred_animation"] = entity.preferred_animation

            self._bind_entity_animation(entity, obj, resolved)

            result.objects.append(obj)
            placed += 1

        if placed:
            info(
                "Imported %d entity mesh(es) into %s/Entities",
                placed,
                parent.name,
            )

        return placed

    def _bind_entity_animation(
        self,
        entity: Object3D,
        mesh_object: Object,
        model_path: Path,
    ) -> None:

        anim_candidates = list(entity.animation_set_paths)

        if not anim_candidates:
            sibling = Path(entity.model_path.replace("\\", "/")).with_suffix(
                ".anim"
            )
            anim_candidates.append(str(sibling).replace("/", "\\"))

        for anim_ref in anim_candidates:
            resolved_anim = resolve_resource_path(
                self.resources_root,
                anim_ref,
            )

            if resolved_anim is None:
                sibling = model_path.with_suffix(".anim")

                if sibling.is_file():
                    resolved_anim = sibling
                else:
                    continue

            if not resolved_anim.is_file():
                continue

            try:
                AnimationFileReader(
                    resolved_anim,
                    self.context,
                    import_source=AnimationImportSource.MESH,
                    target_object=mesh_object,
                ).run()
            except Exception as exc:
                error(
                    "Failed to import animation %s for %s: %s",
                    resolved_anim,
                    entity.model_path,
                    exc,
                )
                return

            if entity.preferred_animation:
                self._apply_preferred_action(
                    mesh_object,
                    resolved_anim.stem,
                    entity.preferred_animation,
                )

            return

        if entity.preferred_animation or entity.animation_set_paths:
            warning(
                "No animation file for entity model %s",
                entity.model_path,
            )

    def _apply_preferred_action(
        self,
        mesh_object: Object,
        anim_stem: str,
        preferred: str,
    ) -> None:

        action_name = f"{anim_stem}:{preferred}"
        armature = None

        for modifier in mesh_object.modifiers:
            if isinstance(modifier, ArmatureModifier) and modifier.object:
                armature = modifier.object
                break

        if armature is None:
            warning(
                "No armature to assign preferred animation %s on %s",
                preferred,
                mesh_object.name,
            )
            return

        action = bpy.data.actions.get(action_name)

        if action is None:
            warning(
                "Preferred animation action %s not found for %s",
                action_name,
                mesh_object.name,
            )
            return

        animation_data = armature.animation_data_create()
        animation_data.action = action

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
