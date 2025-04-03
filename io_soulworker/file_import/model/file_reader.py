from logging import debug, error
from pathlib import Path

import bpy

from bpy.types import (
    Context,
    Material,
    Mesh,
    Object,
    ShaderNodeBsdfPrincipled,
    ShaderNodeTexImage,
    ArmatureModifier,
    VertexGroup
)

from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.readers.wght_reader import WGHTChunkReader
from io_soulworker.chunks.skel_chunk import SkelChunk
from io_soulworker.chunks.subm_chunk import SubmChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.file_import.model.chunk_reader import ModelChunkReader


class NodesHelper:

    @staticmethod
    def create_hair_nodes():
        pass


class NameHelper:

    @staticmethod
    def of_armature_object(name: str) -> str:
        return name + "_a"

    @staticmethod
    def of_armature_modifier(name: str) -> str:
        return name + "_m"


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

    def on_surface(self, chunk: MtrsChunk):

        def create_blender_nodes(material: Material):

            def get_texture_path(path: Path):
                if path.exists() and path.is_file():
                    return path

                error("FILE NOT FOUND %s", path)

                path = self.path.parent / 'Textures' / path.name
                if path.exists() and path.is_file():
                    return path

                error("FILE NOT FOUND %s", path)
                return None

            node_tree = material.node_tree
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
            if path is None:
                error("No textures found for material: %s", material.name)
                return

            texture_node: ShaderNodeTexImage = nodes.new("ShaderNodeTexImage")
            debug("texture path: %s", path)

            texture_node.image = bpy.data.images.load(
                str(path),
                check_existing=True
            )

            debug("texture loaded: %s", path)

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

    def on_mesh(self, chunk: VMshChunk):

        self.mesh_chunk = chunk

        # fill vertices, edges and faces from file
        self.mesh.from_pydata(chunk.vertices, [], chunk.faces)

        uv_layer = self.mesh.uv_layers.new()

        for face in self.mesh.polygons:

            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):

                uv_layer.data[loop_idx].uv = chunk.uvs[vert_idx]

        self.mesh.update()

        self.context.collection.objects.link(self.object)

    def on_skeleton(self, chunk: SkelChunk):

        armature = bpy.data.armatures.new(
            NameHelper.of_armature_object(self.mesh.name)
        )

        armature.display_type = 'STICK'

        armature_object = bpy.data.objects.new(
            NameHelper.of_armature_object(self.mesh.name),
            armature
        )

        modifier: ArmatureModifier = self.object.modifiers.new(
            NameHelper.of_armature_modifier(self.mesh.name),
            'ARMATURE'
        )

        modifier.object = armature_object

        self.context.collection.objects.link(armature_object)
        self.context.view_layer.objects.active = armature_object

        bpy.ops.object.mode_set(mode="EDIT")

        boneParentList: list[str] = []
        boneParentMat = {}

        vertex_groups = self.object.vertex_groups

        self.test_bones = chunk.bones

        for bone in chunk.bones:

            self.vertex_groups.append(vertex_groups.new(name=bone.name))

            boneParentList.append(bone.name)
            new = armature.edit_bones.new(bone.name)

            boneLocalMat = bone.local_space_orientation.to_matrix().to_4x4()
            boneLocalMat.translation = bone.local_space_position

            armature_mat = boneLocalMat

            if (bone.parent_id != SkelChunk.BoneEntity.INVALID_ID):

                id = boneParentList[bone.parent_id]
                armature_mat = boneParentMat[id] @ boneLocalMat

            boneParentMat[bone.name] = armature_mat

            newMatBone = bone.local_space_orientation.to_matrix().to_4x4()
            newMatBone.translation = armature_mat.to_translation()

            new.transform(newMatBone)

            if bone.parent_id != SkelChunk.BoneEntity.INVALID_ID:

                editbone = armature.edit_bones[bone.parent_id]
                new.parent = editbone

                new.head = new.parent.tail

        bpy.ops.object.mode_set(mode="OBJECT")

        bpy.context.view_layer.objects.active = armature_object

        bpy.ops.object.parent_set(type='BONE', keep_transform=True)

        self.context.view_layer.update()

    def on_vertices_material(self, chunk: SubmChunk):

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

        for material in chunk.materials:

            name = materials[material.id].name_full
            vertex_group = vertex_groups.new(name=name)

            start = material.indices_start
            count = start + material.indices_count

            indices = self.mesh_chunk.indices[start: count]
            vertex_group.add(indices, 1, "REPLACE")

            set_material(vertex_group.name, material.id)

            debug("material_id: %d", material.id)
            debug("indices_start: %d", start)
            debug("indices_count: %d", count)

    def on_skeleton_weights(self, reader: WGHTChunkReader):

        count = len(self.mesh.vertices)
        chunks = reader.all_of(count)

        for vertex_index, chunk in enumerate(chunks):

            for entity in chunk.values:

                vertex_group = self.vertex_groups[entity.bone_index]

                vertex_group.add(
                    index=[vertex_index],
                    weight=entity.weight,
                    type="ADD"
                )

# https://youtu.be/UXQGKfCWCBc
# https://youtu.be/6S-0XgGTn-E?list=RD6S-0XgGTn-E
