from typing import Union
import bpy

from bpy.types import Armature, Context, EditBone, ShaderNodeAmbientOcclusion
from bpy.types import Object
from bpy.types import Material
from bpy.types import Mesh
from bpy.types import ShaderNodeTexImage
from bpy.types import Bone
from mathutils import Color, Matrix, Quaternion, Vector

from io_soulworker.core.vis_material import VisMaterial
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_file import VisChunkFile
from io_soulworker.core.utility import indices_to_face
from io_soulworker.core.utility import parse_materials

from pathlib import Path
from struct import unpack
from logging import debug, warn
from logging import error
from io import BufferedReader

from io_soulworker.core.vis_material_transparency import VisMaterialTransparency
from io_soulworker.core.vis_vertex_descriptor import VisVertexDescriptor
from io_soulworker.core.vis_effect_config import VisEffectConfig
from io_soulworker.core.vis_render_state import VisRenderState


class MaterialChunk:
    u1: int
    chunk_name: int
    u2: int
    u3: int
    mat: str
    bytes: list[int]
    specular: str
    diffuse: str
    normal: str
    u4: int
    u5: str
    u6: int
    u7: int
    u8: int
    u9: int
    u10: int
    u11: int
    u12: int
    u13_name: str
    u14_name: str
    u15_name: str
    u16: int
    u17: int
    u18: int
    u19: int

    u20: int
    u21: int
    u22: int


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


class ImportObject(VisChunkFile):
    mesh: Mesh = None
    object: Object = None
    context: Context
    v_materials: dict[str, VisMaterial]
    emission_strength: float

    def __init__(self, path: Path, context: Context, emission_strength: float) -> None:
        super(ImportObject, self).__init__(path)

        self.emission_strength = emission_strength

        # save context
        self.context = context

        # create mesh
        self.mesh: Mesh = bpy.data.meshes.new(self.path.stem)

        # create object
        self.object = bpy.data.objects.new(self.mesh.name, self.mesh)

        # path to data folder
        material_folder = (self.path.with_suffix(self.path.suffix + "_data"))

        # path to material.xml file
        material_path = material_folder / "materials.xml"

        self.v_materials = parse_materials(material_path)

    def on_chunk_start(self, chunk: int, model: BufferedReader) -> None:
        if chunk == VisChunkId.MTRS:
            self.process_mtrs(chunk, model)

        elif chunk == VisChunkId.VMSH:
            self.process_vmsh(chunk, model)

        # elif chunk == VisChunkId.SKEL:
            # self.process_skel(chunk, model)

        elif chunk == VisChunkId.WGHT:
            self.process_wght(chunk, model)

        elif chunk == VisChunkId.SUBM:
            self.process_subm(chunk, model)

    def process_mtrs(self, chunk: int, model: BufferedReader):
        def update_material(material: Material, diffuse_path: str, token: str):
            node_tree = material.node_tree
            nodes = node_tree.nodes

            v_material = self.v_materials.get(token)

            # TODO: use *.vmodel material
            if not v_material:
                error("MATERIAL NOT FOUND %s", token)
                return

            pbsdf_node = nodes.get("Principled BSDF")

            if not v_material.diffuse and not diffuse_path:
                debug("no diffuse")
                ambient_occlusion: ShaderNodeAmbientOcclusion = nodes.new(
                    "ShaderNodeAmbientOcclusion")

                ambient_occlusion.samples = 32

                ambient_occlusion.inputs[0].default_value = [
                    v / 255.0 for v in v_material.ambient]

                node_tree.links.new(
                    pbsdf_node.inputs.get("Base Color"),
                    ambient_occlusion.outputs.get("Color")
                )
            else:
                debug("has diffuse")
                path = self.path.parent / v_material.diffuse

                if not path.exists() or not path.is_file():
                    error("FILE NOT FOUND %s", path)

                    path = self.path.parent / 'Textures' / \
                        Path(diffuse_path.decode('ASCII')).name
                    if not path.exists() or not path.is_file():
                        error("FILE NOT FOUND %s", path)
                        return

                texture_node: ShaderNodeTexImage = nodes.new(
                    "ShaderNodeTexImage")
                debug("texture path: %s", path.as_posix())

                texture_node.image = bpy.data.images.load(path.as_posix())
                debug("texture loaded: %s", path)

                node_tree.links.new(
                    pbsdf_node.inputs.get("Base Color"),
                    texture_node.outputs.get("Color")
                )

                node_tree.links.new(
                    pbsdf_node.inputs.get("Alpha"),
                    texture_node.outputs.get("Alpha")
                )

                if "GLOW" in token:
                    debug("has glow")
                    pbsdf_node.inputs["Emission Strength"].default_value = self.emission_strength

                    node_tree.links.new(
                        pbsdf_node.inputs.get("Emission"),
                        texture_node.outputs.get("Color")
                    )

            if v_material.transparency != VisMaterialTransparency.OPAQUE:
                debug("has alpha")
                material.blend_method = "HASHED"
                material.shadow_method = "HASHED"

            material.alpha_threshold = v_material.alphathreshold

        count, = unpack("<i", model.read(4))

        for _ in range(count):
            u1, = unpack("<i", model.read(4))
            assert u1 == 1

            chunk_name, = unpack("<I", model.read(4))

            u2, = unpack("<i", model.read(4))

            u3, = unpack("<H", model.read(2))
            assert u3 == 6

            mat_length, = unpack("<I", model.read(4))
            mat_name, = unpack("<%ss" % mat_length, model.read(mat_length))
            mat_name = mat_name.decode('ASCII')

            debug("mat_name: %s", mat_name)

            b = model.read(26)

            specular_length, = unpack("<i", model.read(4))
            assert specular_length == 0

            diffuse_length, = unpack("<i", model.read(4))
            assert diffuse_length >= 0

            diffuse_path, = unpack(
                "<%ss" % diffuse_length,
                model.read(diffuse_length))
            debug("inner diffuse path: %s", diffuse_path)

            normal_length, = unpack("<i", model.read(4))
            assert normal_length == 0

            u4, = unpack("<i", model.read(4))

            u5_length, = unpack("<i", model.read(4))
            u5_name, = unpack(
                "<%ss" % u5_length,
                model.read(u5_length)
            )

            debug("u5_name: %s", u5_name)

            u6, u7, u8, u9, u10, u11, u12 = unpack(
                "<iiiiiii",
                model.read(4 * 7)
            )

            u13_length, = unpack("<i", model.read(4))
            u13_name, = unpack("<%ss" % u13_length, model.read(u13_length))
            u13_name = u13_name.decode('ASCII')

            debug("u13_name: %s", u13_name)

            u14_length, = unpack("<i", model.read(4))
            u14_name, = unpack("<%ss" % u14_length, model.read(u14_length))
            u14_name = u14_name.decode('ASCII')

            debug("u14_name: %s", u14_name)

            u15_length, = unpack("<i", model.read(4))
            u15_name, = unpack("<%ss" % u15_length, model.read(u15_length))
            u15_name = u15_name.decode('ASCII')

            debug("u15_name: %s", u15_name)

            u16, u17, u18, u19, = unpack("<iiii", model.read(4 * 4))
            assert u19 == 16777216

            u20, = unpack("<H", model.read(2))
            u21, = unpack("<c", model.read(1))
            u22, = unpack("<i", model.read(4))
            assert u22 == 1297371724

            material = bpy.data.materials.new(self.mesh.name + "_" + mat_name)
            material.use_nodes = True

            self.mesh.materials.append(material)

            update_material(material, diffuse_path, mat_name)

    def process_vmsh(self, chunk: int, model: BufferedReader):
        header, = unpack("<I", model.read(4))
        assert header == chunk

        version, = unpack("<I", model.read(4))
        assert version == 1

        magick, = unpack("<I", model.read(4))
        assert magick == 0x4455ABCD

        v69, = unpack("<i", model.read(4))

        vd = VisVertexDescriptor(model)

        vertex_count, = unpack("<I", model.read(4))
        iMemUsageFlagIndices, = unpack("<B", model.read(1))

        if v69 >= 4:
            iBindFlagVertices, = unpack("<B", model.read(1))
        
        if v69 >= 3:
            bMeshDataIsBigEndian, = unpack("<B", model.read(1))
            v74, = unpack("<H", model.read(2))

        prim_type, = unpack("<I", model.read(4))
        index_count, = unpack("<I", model.read(4))
        index_format, = unpack("<I", model.read(4))
        current_prim_count, = unpack("<I", model.read(4))
        mem_usage_flag_indices, = unpack("<B", model.read(1))
        bind_flag_bertices, = unpack("<B", model.read(1))
        vertices_double_buffered, = unpack("<B", model.read(1))
        indices_double_buffered, = unpack("<B", model.read(1))
        render_state = VisRenderState(model)
        use_projection, = unpack("<B", model.read(1))
        effect_config = VisEffectConfig(model)

        vertices = []
        uv_list = []
        for _ in range(vertex_count):
            t = model.tell()
            vx, vy, vz = unpack("<fff", model.read(12))
            vertices.append([vx, vy, vz])

            tex_coord_offset = t + vd.tex_coord_offset[0].u
            model.seek(tex_coord_offset)
            u, = unpack("<f", model.read(4))

            tex_coord_offset = t + vd.tex_coord_offset[0].v
            model.seek(tex_coord_offset)
            v, = unpack("<f", model.read(4))

            uv_list.append([u, v])

            model.seek(t + vd.stride)

        count = current_prim_count * 3
        self.indices = unpack(f"<{count}H", model.read(count * 2))
        faces = list(indices_to_face(self.indices))

        # fill vertices, edges and faces from file
        self.mesh.from_pydata(vertices, [], faces)

        uv_layer = self.mesh.uv_layers.new()
        for face in self.mesh.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uv_layer.data[loop_idx].uv = [
                    uv_list[vert_idx][0],

                    # flip V
                    -uv_list[vert_idx][1]
                ]

        # recalc normals
        self.mesh.calc_normals()

        # push changes
        self.mesh.update()

        self.context.collection.objects.link(self.object)

    def process_skel(self, chunk: int, model: BufferedReader):
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

        _, count = unpack("<HH", model.read(2 * 2))
        for _ in range(count):
            name_length, = unpack("<I", model.read(4))
            name, = unpack(("<%ss" % name_length), model.read(name_length))

            parent_id, = unpack("<h", model.read(2))

            inverse_object_space_position = Vector(
                unpack("<fff", model.read(4 * 3)))
            inverse_object_space_orientation = Quaternion(
                unpack("<ffff", model.read(4 * 4)))
            local_space_position = Vector(unpack("<fff", model.read(4 * 3)))
            local_space_orientation = Quaternion(
                unpack("<ffff", model.read(4 * 4)))

            name = armature.edit_bones.new(name.decode("ASCII"))
            p = local_space_position
            q = local_space_orientation

            bones.append(Bone(parent_id, name, p, q))

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

    def process_wght(self, chunk: int, model: BufferedReader):
        pass

    def process_subm(self, chunk: int, model: BufferedReader):
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

        u1, u2, u3 = unpack("<iii", model.read(4 * 3))

        count, = unpack("<i", model.read(4))

        materials = self.mesh.materials
        vertex_groups = self.object.vertex_groups

        bpy.context.view_layer.objects.active = self.object

        for _ in range(count):
            indices_start, indices_count, u6, u7, u8, u9, u10, u10 = unpack(
                "<iiiiiiii",
                model.read(4 * 8)
            )

            u11, u12, u13, u14, u15, u16 = unpack(
                "<ffffff",
                model.read(4 * 6)
            )

            material_id, u17 = unpack("<ii", model.read(4 * 2))

            material_name = materials[material_id].name_full
            vertex_group = vertex_groups.new(name=material_name)

            indices = self.indices[indices_start:indices_start + indices_count]
            vertex_group.add(indices, 1, "REPLACE")

            set_material(vertex_group.name, material_id)

            debug("material_id: %d", material_id)
            debug("indices_start: %d", indices_start)
            debug("indices_count: %d", indices_count)


# https://youtu.be/UXQGKfCWCBc
# best music for best coders lol
