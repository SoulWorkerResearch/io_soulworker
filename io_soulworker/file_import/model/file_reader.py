from __future__ import annotations

import bpy

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
from io_soulworker.file_import.shaders.node_groups import (
    apply_shader_to_material,
    arrange_material_nodes,
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
    ) -> None:

        super().__init__(path)

        self.emission_strength = emission_strength
        self.context = context
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

    def _link_object(self) -> None:

        collection = self.target_collection or self.context.collection

        if self.object.name not in collection.objects:
            collection.objects.link(self.object)

    def _apply_transform(self) -> None:

        if self.matrix_world is not None:
            self.object.matrix_world = self.matrix_world

    # @override
    def on_surface(self, chunk: MtrsChunk):

        def create_blender_nodes(material: Material):

            def get_texture_list(base: Path, relative: str):

                clear_path = Path(relative.replace('\\', '/'))

                yield base / clear_path

                yield base.parent / 'Textures' / clear_path.name

            def get_texture_path(base: Path, relative: str):

                for path in get_texture_list(base, relative):

                    if path.exists() and path.is_file():

                        debug("path: %s", path)
                        return path

                    error("FILE NOT FOUND %s", path)

                return None

            node_tree = material.node_tree

            if node_tree is None:

                error("Node tree is None")
                return

            nodes = node_tree.nodes

            pbsdf_node: ShaderNodeBsdfPrincipled = nodes["Principled BSDF"]

            path = get_texture_path(self.path.parent, chunk.diffuse_map)

            debug("texture path: %s", path)

            if path is not None:

                texture_node: ShaderNodeTexImage = nodes.new(
                    "ShaderNodeTexImage")
                texture_node.name = "Diffuse"
                texture_node.label = "Diffuse"
                debug("texture node: %s", texture_node)

                texture_node.image = bpy.data.images.load(
                    str(path),
                    check_existing=True
                )

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

            else:

                error("No textures found for material: %s", material.name)

            if chunk.transparency_type != VisTransparencyType.NONE:

                debug("has alpha")

            xml_material = self.xml_materials.get(chunk.name)

            if xml_material is not None and xml_material.shader is not None:

                apply_shader_to_material(material, xml_material.shader)

            arrange_material_nodes(node_tree)

        material = bpy.data.materials.new(chunk.name)
        material.use_nodes = True

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

        self.bone_index_to_vertex_group = {}

        vertex_groups = self.object.vertex_groups

        for bone in chunk.bones:

            vertex_group = vertex_groups.new(name=bone.name)

            self.vertex_groups.append(vertex_group)
            self.bone_index_to_vertex_group[bone.id] = vertex_group

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
