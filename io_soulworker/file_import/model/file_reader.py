import bpy

from logging import debug, error
from pathlib import Path
from typing import final
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

from bpy.types import (
    Context,
    Material,
    Mesh,
    Object,
    ShaderNodeBsdfPrincipled,
    ShaderNodeTexImage,
    ArmatureModifier,
    VertexGroup,
)


class NodesHelper:

    @staticmethod
    def create_hair_nodes():

        pass


@final
class ModelFileReader(ModelChunkReader):

    mesh: Mesh
    object: Object
    context: Context
    emission_strength: float

    # index - bone id
    vertex_groups: list[VertexGroup] = []

    def __init__(self, path: Path, context: Context, emission_strength: float) -> None:

        super().__init__(path)

        self.emission_strength = emission_strength

        # save context
        self.context = context

        # create mesh
        self.mesh = bpy.data.meshes.new(self.path.stem)

        # create object
        self.object = bpy.data.objects.new(self.mesh.name, self.mesh)
        self.vertex_groups = []

    # @override
    def on_surface(self, chunk: MtrsChunk):

        def create_blender_nodes(material: Material):

            def get_texture_path(path: Path):

                if path.exists() and path.is_file():

                    return path

                error("FILE NOT FOUND %s", path)

                path = self.path.parent / 'Textures' / path.name
                debug("path: %s", path)

                if path.exists() and path.is_file():

                    return path

                error("FILE NOT FOUND %s", path)

                return None

            node_tree = material.node_tree

            if node_tree is None:

                error("Node tree is None")
                return

            nodes = node_tree.nodes

            pbsdf_node: ShaderNodeBsdfPrincipled = nodes["Principled BSDF"]

            # if not v_material.diffuse_map:
            #     debug("no diffuse_map")
            #     ambient_occlusion: ShaderNodeAmbientOcclusion = nodes.new(4
            #         "ShaderNodeAmbientOcclusion")

            #     ambient_occlusion.samples = 32

            #     ambient_occlusion.inputs[0].default_value = [
            #         v / 255.0 for v in v_material.ambient]

            #     node_tree.links.new(
            #         pbsdf_node.inputs.get("Base Color"),
            #         ambient_occlusion.outputs.get("Color")
            #     )
            # else:

            path = get_texture_path(self.path.parent / chunk.diffuse_map)
            debug("texture path: %s", path)
            if path is None:

                error("No textures found for material: %s", material.name)
                return

            texture_node: ShaderNodeTexImage = nodes.new("ShaderNodeTexImage")
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

                # pbsdf_node.inputs["Emission Strength"].default_value = self.emission_strength

                node_tree.links.new(
                    pbsdf_node.inputs["Emission Strength"],
                    texture_node.outputs["Alpha"]
                )

                node_tree.links.new(
                    pbsdf_node.inputs["Emission Color"],
                    texture_node.outputs["Color"]
                )

            if chunk.transparency_type != VisTransparencyType.NONE:

                debug("has alpha")

                # material.blend_method = "HASHED"
                # material.shadow_method = "HASHED"

            # material.alpha_threshold = v_material.alphathreshold

        material = bpy.data.materials.new(chunk.name)
        material.use_nodes = True

        create_blender_nodes(material)

        self.mesh.materials.append(material)

    # @override
    def on_mesh(self, chunk: VMshChunk):

        self.mesh_chunk = chunk

        # fill vertices, edges and faces from file
        self.mesh.from_pydata(chunk.vertices, [], chunk.faces)

        uv_layer = self.mesh.uv_layers.new()

        for face in self.mesh.polygons:

            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):

                uv_layer.uv[loop_idx].vector = chunk.uvs[vert_idx]

        self.mesh.update()

        self.context.collection.objects.link(self.object)

    # @override
    def on_skeleton(self, chunk: VisSkeletonChunk_cl):

        result = build_armature_from_skeleton(
            self.context,
            self.mesh.name,
            chunk,
        )

        modifier: ArmatureModifier = self.object.modifiers.new(
            NameHelper.of_armature_modifier(self.mesh.name),
            'ARMATURE'
        )

        modifier.object = result.object

        self.bone_index_to_vertex_group = {}  # Map bone index to vertex group

        vertex_groups = self.object.vertex_groups

        for bone in chunk.bones:

            vertex_group = vertex_groups.new(name=bone.name)

            self.vertex_groups.append(vertex_group)
            self.bone_index_to_vertex_group[bone.id] = vertex_group

    # @override
    def on_sub_mesh(self, chunk: VisSubMeshChunk):

        # TODO: i have no idea how this can be done without touching the interface.
        #       hope someone can help me with this.
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

                # Use the bone index mapping to get the correct vertex group
                if entity.bone_index in self.bone_index_to_vertex_group:

                    vertex_group = self.bone_index_to_vertex_group[entity.bone_index]

                    vertex_group.add(
                        index=[vertex_index],
                        weight=entity.weight,
                        type="ADD"
                    )

                else:

                    debug(
                        f"Warning: bone_index {entity.bone_index} not found in vertex groups")

# https://youtu.be/UXQGKfCWCBc
# https://youtu.be/6S-0XgGTn-E?list=RD6S-0XgGTn-E
