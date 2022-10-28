import bmesh
import bpy

from bpy.types import Context
from bpy.types import EditBone
from bpy.types import Object
from bpy.types import Mesh
from bpy.types import ShaderNodeTexImage
from bpy.types import Material

from mathutils import Matrix
from mathutils import Quaternion
from mathutils import Vector

from struct import unpack
from pathlib import Path
from logging import debug
from logging import error
from io_soulworker.chunks.skel_chunk import SkelChunk

from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.subm_chunk import SubmChunk, VisVerticesMaterial
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.out.model_file_reader import ModelFileReader


class SkelValue:

    name: str
    parent_id: int
    inverse_object_space_position: Vector
    inverse_object_space_orientation: Quaternion
    local_space_position: Vector
    local_space_orientation: Quaternion

    def __init__(self, name: str, parent_id: int, inverse_object_space_position: Vector, inverse_object_space_orientation: Quaternion, local_space_position: Vector, local_space_orientation: Quaternion) -> None:
        self.name = name
        self.parent_id = parent_id
        self.inverse_object_space_position = inverse_object_space_position
        self.inverse_object_space_orientation = inverse_object_space_orientation
        self.local_space_position = local_space_position
        self.local_space_orientation = local_space_orientation


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

            if chunk.ui_transparency_type != VisTransparencyType.NONE:
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
        self.mesh.calc_normals()
        self.mesh.update()

        self.context.collection.objects.link(self.object)

    def process_skel(self, chunk: VisChunkId, reader: BinaryReader):
        class Bone:
            parent_id: int
            pos: Vector
            rot: Quaternion
            obj: EditBone

            def __init__(self, parent_id: int, obj: EditBone, pos: Vector, rot: Quaternion) -> None:
                self.parent_id = parent_id
                self.pos = pos
                self.rot = rot
                self.obj = obj

        armature = bpy.data.armatures.new(self.mesh.name)
        armature_object = bpy.data.objects.new(armature.name, armature)

        modifier = self.object.modifiers.new(armature.name, 'ARMATURE')
        modifier.object = armature_object

        self.context.collection.objects.link(armature_object)

        bpy.context.view_layer.objects.active = armature_object

        bpy.ops.object.mode_set(mode="EDIT")
        # ---------------
        bpy.types.Bone.AxisRollFromMatrix
        armature = bpy.data.armatures.get("Armature")
        for bone in armature.edit_bones.values():
            armature.edit_bones.remove(bone)

        bone = armature.edit_bones.new('asd')

        bone.head = [0, 0, 0]
        bone.tail = [0, 0, 10]
        # ---------------

        bones: list[Bone] = []

        _, count = unpack("<HH", reader.read(2 * 2))
        for _ in range(count):
            name = reader.read_utf8_uint32_string()

            parent_id = reader.read_uint16()

            inverse_object_space_position = reader.read_float_vector3()
            inverse_object_space_orientation = reader.read_quaternion()
            local_space_position = reader.read_float_vector3()
            local_space_orientation = reader.read_quaternion()

            name = armature.edit_bones.new(name.decode("ASCII"))
            pos = local_space_position
            ori = local_space_orientation

            bones.append(Bone(parent_id, name, pos, ori))

        for bone in bones:
            if bone.parent_id == -1:
                continue

            obj = bones[bone.parent_id].obj
            bone.obj.parent = obj

        for bone in bones:
            if bone.parent_id != -1:
                m1 = Matrix.Translation(
                    bone.pos) @ Matrix(bone.obj.parent.matrix)
                m2: Matrix = m1 + Matrix.Translation(bone.obj.parent.head)
                bone.obj.head = m2.to_translation()

                m: Matrix = bone.rot.to_matrix().to_4x4().inverted() * \
                    Matrix(bone.obj.parent.matrix).to_4x4()
                bone.obj.matrix = m
            else:
                bone.obj.head = Matrix.Translation(bone.pos).to_translation()
                bone.obj.matrix = bone.rot.to_matrix().to_4x4().inverted()

        bpy.ops.object.mode_set(mode="OBJECT")

    # def process_wght(self, chunk: VisChunkId, reader: BinaryReader):
    #     pass

    def on_skeleton(self, chunk: SkelChunk):
        pass
        # armature = bpy.data.armatures.new(self.mesh.name)
        # armature_object = bpy.data.objects.new(armature.name, armature)

        # self.context.collection.objects.link(armature_object)
        # self.context.view_layer.objects.active = armature_object

        # bpy.ops.object.mode_set(mode="EDIT")

        # for bone in chunk.bones:
        #     new = armature.edit_bones.new(bone.name)

        #     if bone.parent_id in chunk.bones:
        #         new.parent = armature.bones.get(chunk.bones[bone.parent_id])
        #         new.head = bone.local_space_position
        #         new.head.rotate(bone.local_space_orientation.to_euler())

        # bpy.ops.object.mode_set(mode="OBJECT")

        # bpy.ops.mesh.primitive_cube_add(location=bone.local_space_position)

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
