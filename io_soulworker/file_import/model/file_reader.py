from __future__ import annotations

import bpy

from json import dumps
from logging import debug, error, warning
from pathlib import Path
from typing import final

from bpy.types import (
    ArmatureModifier,
    Collection,
    Context,
    Material,
    Mesh,
    Object,
    ShaderNodeBsdfPrincipled,
    ShaderNodeTexImage,
    VertexGroup,
)
from mathutils import Matrix

from io_soulworker.chunks.bbbx_chunk import BBBXChunk
from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.readers.wght_reader import WGHTChunkReader
from io_soulworker.chunks.skel_chunk import VisSkeletonChunk_cl
from io_soulworker.chunks.subm_chunk import VisSubMeshChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.file_import.armature_builder import (
    NameHelper,
    build_armature_from_skeleton,
)
from io_soulworker.file_import.model.chunk_reader import ModelChunkReader
from io_soulworker.file_import.model.surface_nodes import apply_surface_params
from io_soulworker.file_import.resource_path import (
    is_builtin_texture,
    load_blender_image,
    resolve_resource_path,
)
from io_soulworker.file_import.shaders.node_groups import (
    apply_shader_to_material,
    arrange_material_nodes,
    library_stem_from_path,
)
from io_soulworker.unit_scale import vision_to_blender

# Resolved path → shared Mesh datablock (materials live on the mesh).
_MESH_CACHE: dict[str, Mesh] = {}


def clear_mesh_cache() -> None:
    """Drop shared mesh references (datablocks themselves stay in ``bpy.data``)."""

    _MESH_CACHE.clear()


def mesh_cache_key(path: Path) -> str:
    return str(path.resolve())


def _live_cached_mesh(key: str) -> Mesh | None:
    """Return the cached mesh if it still exists in this ``.blend``.

    ``orphans_purge`` and File → New leave Python references to removed IDs.
    Accessing those raises ``ReferenceError: StructRNA of type Mesh has been
    removed``.
    """

    mesh = _MESH_CACHE.get(key)
    if mesh is None:
        return None

    try:
        mesh.name
    except ReferenceError:
        del _MESH_CACHE[key]
        return None

    return mesh


class NodesHelper:

    @staticmethod
    def create_hair_nodes():

        pass


@final
class ModelFileReader(ModelChunkReader):
    """Load a ``.model`` / ``.vmesh`` into Blender.

    Can reuse a previously loaded mesh datablock (scene static-mesh instances)
    and place the resulting object with an optional world matrix.
    """

    mesh: Mesh
    object: Object
    context: Context
    emission_strength: float
    vertex_groups: list[VertexGroup]

    def __init__(
        self,
        path: Path,
        context: Context,
        emission_strength: float,
        *,
        collection: Collection | None = None,
        matrix_world: Matrix | None = None,
        object_name: str | None = None,
        reuse_mesh: bool = True,
        resources_root: Path | str | None = None,
    ) -> None:

        super().__init__(path)

        self.emission_strength = emission_strength
        self.context = context
        self.resources_root = Path(resources_root) if resources_root else None
        self.target_collection = collection
        self.matrix_world = matrix_world
        self.reuse_mesh = reuse_mesh
        self.vertex_groups = []
        self.bone_index_to_vertex_group: dict[int, VertexGroup] = {}
        self._cache_key = mesh_cache_key(path)
        self._from_cache = False

        name = object_name or self.path.stem
        cached = _live_cached_mesh(self._cache_key) if reuse_mesh else None

        if cached is not None:
            self.mesh = cached
            self.object = bpy.data.objects.new(name, self.mesh)
            self._from_cache = True
        else:
            self.mesh = bpy.data.meshes.new(self.path.stem)
            self.object = bpy.data.objects.new(name, self.mesh)

        self.mesh["soulworker_source_path"] = self._cache_key

    def run(self):
        """Parse (unless mesh is cached), link, place; return the Blender object."""

        if self._from_cache:
            self._link_object()
            self._apply_transform()
            return self.object

        super().run()

        if self.reuse_mesh:
            _MESH_CACHE[self._cache_key] = self.mesh

        self._apply_transform()
        return self.object

    def _resources_root(self) -> Path | None:
        """Explicit resources root, else the N-panel setting, else ``None``."""

        if self.resources_root is not None and self.resources_root.is_dir():

            return self.resources_root

        scene = getattr(self.context, "scene", None)
        raw = (getattr(scene, "soulworker_unpack_resources", "") or "").strip()

        if not raw:

            return None

        root = Path(bpy.path.abspath(raw))

        return root if root.is_dir() else None

    def _link_object(self) -> None:

        collection = self.target_collection or self.context.collection

        if self.object.name not in collection.objects:
            collection.objects.link(self.object)

    def _apply_transform(self) -> None:
        """Place the mesh and any armature modifiers with the same world matrix.

        Scene entity import moves the mesh via ``matrix_world``. The armature
        must share that transform; otherwise skinning evaluates against an
        armature left at the origin and the mesh explodes.
        """

        if self.matrix_world is None:
            return

        for modifier in self.object.modifiers:
            if (
                isinstance(modifier, ArmatureModifier)
                and modifier.object is not None
            ):
                modifier.object.matrix_world = self.matrix_world

        # Set the child after its armature, so scene placement is applied once.
        self.object.matrix_world = self.matrix_world

    # @override
    def on_surface(self, chunk: MtrsChunk):

        def create_blender_nodes(material: Material):

            def get_texture_list(base: Path, relative: str):

                clear_path = Path(relative.replace('\\', '/'))

                yield base / clear_path

                yield base / 'Textures' / clear_path.name

                yield base.parent / 'Textures' / clear_path.name

                # Vision also resolves paths against the project root, which
                # is where ``\\World\\Textures\\x.dds`` style references live.
                root = self._resources_root()

                if root is not None:

                    yield root / clear_path.relative_to(clear_path.anchor)

            def get_texture_path(base: Path, relative: str):

                if not relative or is_builtin_texture(relative):

                    debug("built-in or empty texture: %r", relative)
                    return None

                for path in get_texture_list(base, relative):

                    resolved = resolve_resource_path(base, str(path))
                    if resolved is not None:

                        debug("path: %s", resolved)
                        return resolved

                    debug("texture candidate not found: %s", path)

                error("FILE NOT FOUND %s (tried mesh dir, Textures/, root)",
                      relative)

                return None

            node_tree = material.node_tree

            if node_tree is None:

                error("Node tree is None")
                return

            nodes = node_tree.nodes

            pbsdf_node: ShaderNodeBsdfPrincipled = nodes["Principled BSDF"]

            path = get_texture_path(self.path.parent, chunk.diffuse_map)

            debug("texture path: %s", path)

            image = load_blender_image(path) if path is not None else None

            if image is not None:

                texture_node: ShaderNodeTexImage = nodes.new(
                    "ShaderNodeTexImage")
                texture_node.name = "Diffuse"
                texture_node.label = "Diffuse"
                debug("texture node: %s", texture_node)

                texture_node.image = image

                debug("texture loaded: %s", texture_node.image.name_full)

                node_tree.links.new(
                    pbsdf_node.inputs["Base Color"],
                    texture_node.outputs["Color"]
                )

                node_tree.links.new(
                    pbsdf_node.inputs["Alpha"],
                    texture_node.outputs["Alpha"]
                )

                if "MO_HAIR" in material.name:

                    NodesHelper.create_hair_nodes()

                if "GLOW" in material.name:

                    debug("has glow")

                    node_tree.links.new(
                        pbsdf_node.inputs["Emission Strength"],
                        texture_node.outputs["Alpha"]
                    )

                    node_tree.links.new(
                        pbsdf_node.inputs["Emission Color"],
                        texture_node.outputs["Color"]
                    )

            elif chunk.diffuse_map and not is_builtin_texture(chunk.diffuse_map):

                error("No textures found for material: %s", material.name)

            apply_surface_params(
                material,
                pbsdf_node,
                chunk,
                resolve_texture=lambda relative: get_texture_path(
                    self.path.parent,
                    relative,
                ),
            )

            if chunk.transparency_type != VisTransparencyType.NONE:

                debug("has alpha")

            xml_material = self.xml_materials.get(chunk.name)

            if xml_material is not None and xml_material.shader is not None:

                apply_shader_to_material(
                    material, xml_material.shader, self._resources_root())

            arrange_material_nodes(node_tree)

        material = bpy.data.materials.new(chunk.name)
        material.use_nodes = True
        material["soulworker_diffuse"] = chunk.diffuse_map
        material["soulworker_material_name"] = chunk.name
        material["soulworker_specular"] = chunk.specular_map
        material["soulworker_normal"] = chunk.normal_map
        material["soulworker_source_directory"] = str(
            self.path.parent.resolve())

        xml_material = self.xml_materials.get(chunk.name)
        if xml_material is not None and xml_material.shader is not None:
            shader = xml_material.shader
            material["soulworker_shader_library"] = library_stem_from_path(
                shader.library)
            material["soulworker_shader_effect"] = shader.effect
            material["soulworker_shader_paramstring"] = shader.paramstring.to_string()
            library = resolve_resource_path(self.path.parent, shader.library)
            if library is not None:
                material["soulworker_shader_library_path"] = str(library)
            root = self._resources_root()
            if root is not None:
                material["soulworker_resources_root"] = str(root)

        # Surface fields the Blender node tree cannot express (transparency
        # mode, alpha threshold, ambient, flags...). Export replays them so a
        # round trip keeps the original look instead of guessing from nodes.
        material["soulworker_mtrs"] = dumps(chunk.to_dict())

        if xml_material is not None and xml_material.attributes:
            material["soulworker_material_xml"] = dumps(
                xml_material.attributes)

        create_blender_nodes(material)

        self.mesh.materials.append(material)

    # @override
    def on_mesh(self, chunk: VMshChunk):

        self.mesh_chunk = chunk

        vertices = [vision_to_blender(vertex) for vertex in chunk.vertices]
        self.mesh.from_pydata(vertices, [], chunk.faces)

        uv_layer = self.mesh.uv_layers.new()

        for face in self.mesh.polygons:

            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):

                uv_layer.uv[loop_idx].vector = chunk.uvs[vert_idx]

        self.mesh.update()

        if self.mesh.validate(verbose=True):
            warning("Mesh had issues and was corrected: %s", self.mesh.name)

        if hasattr(self.mesh, "shade_smooth"):

            self.mesh.shade_smooth()

        if chunk.normals and len(chunk.normals) == len(self.mesh.vertices):

            self.mesh.normals_split_custom_set_from_vertices(
                [tuple(normal) for normal in chunk.normals]
            )
            self.mesh.update()

        self._link_object()

    # @override
    def on_skeleton(self, chunk: VisSkeletonChunk_cl):

        result = build_armature_from_skeleton(
            self.context,
            self.mesh.name,
            chunk,
            collection=self.target_collection,
        )

        modifier: ArmatureModifier = self.object.modifiers.new(
            NameHelper.of_armature_modifier(self.mesh.name),
            'ARMATURE'
        )

        modifier.object = result.object

        # Object root-motion tracks must carry the mesh with the armature.
        # Without parenting, Blender transforms the stationary mesh into the
        # moving armature's space before skinning, distorting the character.
        self.object.parent = result.object
        self.object.matrix_parent_inverse = Matrix.Identity(4)

        self.bone_index_to_vertex_group = {}

        vertex_groups = self.object.vertex_groups

        for bone in chunk.bones:

            vertex_group = vertex_groups.new(name=bone.name)

            self.vertex_groups.append(vertex_group)
            self.bone_index_to_vertex_group[bone.id] = vertex_group

    # @override
    def on_bounding_boxes(self, chunk: BBBXChunk):
        """Keep the per-bone boxes so an export can replay them verbatim.

        Vision stores one box per bone in bone space. The 3ds Max exporter
        derives them from Biped geometry, not from skinned vertices, so they
        cannot be rebuilt from Blender data.
        """

        armature_object = self.object.parent

        if armature_object is None or armature_object.type != "ARMATURE":
            return

        names = list(armature_object.get("soulworker_bone_names_by_index", []))

        if len(names) != len(chunk.values):
            return

        armature_object["soulworker_bone_bounds"] = dumps([
            {
                "name": name,
                "min": [entity.bounds.min.x, entity.bounds.min.y,
                        entity.bounds.min.z],
                "max": [entity.bounds.max.x, entity.bounds.max.y,
                        entity.bounds.max.z],
            }
            for name, entity in zip(names, chunk.values)
        ])

    # @override
    def on_sub_mesh(self, chunk: VisSubMeshChunk):

        def set_material(vertex_group_name: str, material_id: int):

            bpy.ops.object.mode_set(mode="EDIT")

            bpy.ops.object.vertex_group_set_active(group=vertex_group_name)
            bpy.ops.object.vertex_group_select()

            self.object.active_material_index = material_id

            bpy.ops.object.material_slot_assign()
            bpy.ops.mesh.select_all(action="DESELECT")

            bpy.ops.object.mode_set(mode="OBJECT")

        materials = self.mesh.materials
        vertex_groups = self.object.vertex_groups

        bpy.context.view_layer.objects.active = self.object

        for mesh in chunk.meshes:

            name = materials[mesh.surface_index].name_full
            vertex_group = vertex_groups.new(name=name)

            start = mesh.indices_start
            count = start + mesh.indices_count

            indices = self.mesh_chunk.indices[start: count]
            vertex_group.add(indices, 1, "REPLACE")

            set_material(vertex_group.name, mesh.surface_index)

            debug("material_id: %d", mesh.surface_index)
            debug("indices_start: %d", start)
            debug("indices_count: %d", count)

    # @override
    def on_skeleton_weights(self, reader: WGHTChunkReader):

        count = len(self.mesh.vertices)
        chunks = reader.all_of(count)

        for vertex_index, chunk in enumerate(chunks):

            for entity in chunk.values:

                if entity.bone_index in self.bone_index_to_vertex_group:

                    vertex_group = self.bone_index_to_vertex_group[entity.bone_index]

                    vertex_group.add(
                        index=[vertex_index],
                        weight=entity.weight,
                        type="ADD"
                    )

                else:

                    debug(
                        f"Warning: bone_index {
                            entity.bone_index} not found in vertex groups")
