import bpy

from bpy.types import Context
from bpy.types import EditBone
from bpy.types import Object
from bpy.types import Mesh
from bpy.types import ShaderNodeTexImage
from bpy.types import Material
from bpy.types import Armature

from mathutils import Matrix
from mathutils import Quaternion
from mathutils import Vector

from pathlib import Path
from logging import debug
from logging import error

from io_soulworker.chunks.skel_chunk import SkelChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.subm_chunk import SubmChunk
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.out.model_file_reader import ModelFileReader


class ModelImporter(ModelFileReader):

    mesh: Mesh = None
    object: Object = None
    context: Context
    emission_strength: float

    def __init__(self, path: Path, context: Context, emission_strength: float) -> None:

        super().__init__(path)

        self.emission_strength = emission_strength

        # save context
        self.context = context

        # create mesh
        self.mesh: Mesh = bpy.data.meshes.new(self.path.stem)

        # create object
        self.object = bpy.data.objects.new(self.mesh.name, self.mesh)

    def on_surface(self, chunk: MtrsChunk):

        def create_blender_nodes(material: Material):

            node_tree = material.node_tree
            nodes = node_tree.nodes

            pbsdf_node = nodes.get("Principled BSDF")

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

            path = self.path.parent / chunk.diffuse_map

            if not path.exists() or not path.is_file():
                error("FILE NOT FOUND %s", path)

                path = self.path.parent / 'Textures' / path.name
                if not path.exists() or not path.is_file():
                    error("FILE NOT FOUND %s", path)
                    return

            texture_node: ShaderNodeTexImage = nodes.new("ShaderNodeTexImage")
            debug("texture path: %s", path)

            texture_node.image = bpy.data.images.load(path.__str__())
            debug("texture loaded: %s", path)

            node_tree.links.new(
                pbsdf_node.inputs.get("Base Color"),
                texture_node.outputs.get("Color")
            )

            node_tree.links.new(
                pbsdf_node.inputs.get("Alpha"),
                texture_node.outputs.get("Alpha")
            )

            if "GLOW" in material.name:
                debug("has glow")
                pbsdf_node.inputs["Emission Strength"].default_value = self.emission_strength

                node_tree.links.new(
                    pbsdf_node.inputs.get("Emission"),
                    texture_node.outputs.get("Color")
                )

            if chunk.transparency_type != VisTransparencyType.NONE:
                material.blend_method = "HASHED"
                material.shadow_method = "HASHED"

                debug("has alpha")

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

        # self.mesh.normals_split_custom_set(chunk.normals)
        self.mesh.update()

        self.context.collection.objects.link(self.object)

    def on_skeleton(self, chunk: SkelChunk):

        armature = bpy.data.armatures.new(self.mesh.name + "_a")
        armature.display_type = 'STICK'
        armature_object = bpy.data.objects.new(armature.name + "_o", armature)

        modifier = self.object.modifiers.new(armature.name + "_m", 'ARMATURE')
        modifier.object = armature_object

        self.context.collection.objects.link(armature_object)

        bpy.context.view_layer.objects.active = armature_object

        def __create_bones(armature: Armature, chunk: SkelChunk):

            for bone in chunk.bones:
                armature.edit_bones.new(bone.name)

        def __update_connections(armature: Armature, chunk: SkelChunk):

            for bone in chunk.bones:
                obj: EditBone = armature.edit_bones.get(bone.name)

                if 0 > bone.parent_id or bone.parent_id > len(chunk.bones):
                    debug('bad bone parent index: %d', bone.parent_id)
                    continue

                parent = chunk.bones[bone.parent_id]
                value = armature.edit_bones.get(parent.name)

                if not isinstance(value, EditBone):
                    debug('baparent bone not found: %s', parent.name)
                    continue

                obj.parent = value

        def __update_positions(armature: Armature, chunk: SkelChunk):

            for bone in chunk.bones:
                obj: EditBone = armature.edit_bones.get(bone.name)

                if obj.parent:
                    src = next(
                        (v for v in chunk.bones if v.name == obj.parent.name), None)

                    if src is None:
                        raise

                    src.inverse_object_space_orientation.to_axis_angle()

                    obj.tail = src.local_space_position
                    obj.head = bone.local_space_position
                else:
                    obj.tail = (0, 0, 0)
                    obj.head = bone.local_space_position

        bpy.ops.object.mode_set(mode="EDIT")

        __create_bones(armature, chunk)
        __update_connections(armature, chunk)
        __update_positions(armature, chunk)

        bpy.ops.object.mode_set(mode="OBJECT")

        armature_object.update_from_editmode()

    # def process_wght(self, chunk: VisChunkId, reader: BinaryReader):
    #     pass

    def on_vertices_material(self, chunk: SubmChunk):

        # TODO: i have no idea how this can be done without touching the interface.
        # hope someone can help me with this.
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

            indices = self.mesh_chunk.indices[material.indices_start:
                                              material.indices_start + material.indices_count]
            vertex_group.add(indices, 1, "REPLACE")

            set_material(vertex_group.name, material.id)

            debug("material_id: %d", material.id)
            debug("indices_start: %d", material.indices_start)
            debug("indices_count: %d", material.indices_count)


# https://youtu.be/UXQGKfCWCBc
# best music for best coders lol
