import bpy

from bpy.types import Context
from bpy.types import EditBone
from bpy.types import ShaderNodeAmbientOcclusion
from bpy.types import Object
from bpy.types import Material
from bpy.types import Mesh
from bpy.types import ShaderNodeTexImage
from mathutils import Matrix
from mathutils import Quaternion
from mathutils import Vector

from pathlib import Path
from struct import unpack
from logging import debug
from logging import error
from io import BufferedReader


from io_soulworker.core.vis_material import VisMaterial
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_file import VisChunkFile
from io_soulworker.core.utility import indices_to_face
from io_soulworker.core.utility import read_mesh_config_effects
from io_soulworker.core.utility import read_color
from io_soulworker.core.utility import read_string
from io_soulworker.core.utility import parse_materials
from io_soulworker.core.vis_material_transparency import VisMaterialTransparency
from io_soulworker.core.vis_vertex_descriptor import VisVertexDescriptor
from io_soulworker.core.vis_mesh_effect_config import VisMeshEffectConfig
from io_soulworker.core.vis_render_state import VisRenderState


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

    def process_mtrs(self, chunk: int, reader: BufferedReader):
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

        count, = unpack("<I", reader.read(4))
        for _ in range(count):
            u1, = unpack("<I", reader.read(4))
            assert u1 == 1

            chunk_name, = unpack("<i", reader.read(4))
            assert chunk_name == VisChunkId.MTRL

            u2, = unpack("<I", reader.read(4))

            v23, = unpack("<H", reader.read(2))

            mat_name = read_string(reader)
            debug("mat_name: %s", mat_name)

            # casted to VSurfaceFlags_e (combinable)
            flags, = unpack("<I", reader.read(4))

            # internal sorting key; has to be in the range 0..15
            ui_sorting_key, = unpack("<I", reader.read(4))

            # specular multiplier
            spec_mul, = unpack("<f", reader.read(4))

            # specular exponent
            spec_exp, = unpack("<f", reader.read(4))

            # casted to VIS_TransparencyType
            ui_transparency_type, = unpack("<B", reader.read(1))

            # material ID that is written to G-Buffer in deferred rendering
            ui_deferred_id, = unpack("<B", reader.read(1))

            if v23 >= 3:
                depth_bias, = unpack("<f", reader.read(4))

            if v23 >= 4:
                depth_bias_clamp, = unpack("<f", reader.read(4))
                slope_scaled_depth_bias, = unpack("<f", reader.read(4))

            diffuse_map = read_string(reader)
            debug("inner diffuse path: %s", diffuse_map)

            specular_map = read_string(reader)
            debug("inner specular path: %s", specular_map)

            normal_map = read_string(reader)
            debug("inner normal path: %s", normal_map)

            if v23 >= 2:
                count, = unpack("<I", reader.read(4))
                aux_filenames = [read_string(reader) for _ in range(count)]

                for filename in aux_filenames:
                    debug("aux filename: %s", filename)

            user_data = read_string(reader)
            user_flags, = unpack("<I", reader.read(4))
            ambient_color = read_color(reader)
            v19, = unpack("<I", reader.read(4))
            v18, = unpack("<I", reader.read(4))
            parallax_scale, = unpack("<f", reader.read(4))
            parallax_bias, = unpack("<f", reader.read(4))
            config_effects = read_mesh_config_effects(reader)

            if v23 >= 5:
                override_library = read_string(reader)
                override_material = read_string(reader)

            if v23 >= 6:
                ui_mobile_shader_flags, = unpack("<I", reader.read(4))
                
            u1, = unpack("<I", reader.read(4))
            assert u1 == 1

            chunk_name, = unpack("<I", reader.read(4))
            assert chunk_name == VisChunkId.MTRL

            material = bpy.data.materials.new(self.mesh.name + "_" + mat_name)
            material.use_nodes = True

            self.mesh.materials.append(material)

            update_material(material, diffuse_map, mat_name)

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
        effect_config = VisMeshEffectConfig(model)

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
            name = read_string(model)

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
