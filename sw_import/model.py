import bpy

from bpy.props import CollectionProperty
from bpy.props import StringProperty
from bpy.props import BoolProperty
from bpy.types import Context
from bpy.types import LayerCollection
from bpy.types import Collection
from bpy.types import Object
from bpy.types import ShaderNodeAddShader
from bpy.types import ShaderNodeEmission
from bpy.types import ShaderNodeOutputMaterial
from bpy.types import Material
from bpy.types import Mesh
from bpy.types import Operator
from bpy.types import PropertyGroup
from bpy.types import ShaderNodeTexImage
from bpy_extras.io_utils import ImportHelper

from io_soulworker.core.v_material import VMaterial
from io_soulworker.core.v_chunk_id import VChunkId
from io_soulworker.core.v_chunk_file import VChunkFile
from io_soulworker.core.utility import indices_to_face
from io_soulworker.core.utility import parse_materials

from pathlib import Path
from struct import unpack
from logging import debug
from logging import error
from io import BufferedReader
from io import SEEK_CUR


class ImportModelRunner(Operator, ImportHelper):
    bl_idname = "import_model.helper"
    bl_label = "Select"

    is_create_collection: BoolProperty(
        name="Create collection",
        default=True,
    )

    # selected files
    files: CollectionProperty(type=PropertyGroup)

    def get_layer_collection(self, layer_collection: LayerCollection, collection: Collection):
        found = None

        if (layer_collection.name == collection.name):
            return layer_collection

        for layer in layer_collection.children:
            found = self.get_layer_collection(layer, collection)

            if found:
                return found

    def create_collection(self, context: Context, name: str):
        # collection for loaded object
        collection = bpy.data.collections.new(name)

        # link collection for user access
        context.collection.children.link(collection)

        view_layer = context.view_layer

        # get layer of linked collection
        layer_collection = view_layer.layer_collection

        # set created collection as active collection
        view_layer.active_layer_collection = self.get_layer_collection(
            layer_collection,
            collection
        )

    def execute(self, context: Context):
        context.scene.render.engine = "BLENDER_EEVEE"

        root = Path(self.properties.filepath)

        if self.is_create_collection:
            self.create_collection(context, root.parent.name)

        for file in self.files:
            path: Path = root.parent / file.name

            if not path.is_file() or path.suffix != ".model":
                error("bad path, skipped: %s", path)
                continue

            importer = ImportModel(path, context)
            importer.run()

        return {"FINISHED"}


class ImportModel(VChunkFile):
    mesh: Mesh = None
    object: Object = None
    context: Context
    v_materials: dict[str, VMaterial]

    def __init__(self, path: Path, context: Context) -> None:
        super(ImportModel, self).__init__(path)

        # save context
        self.context = context

        # create mesh
        self.mesh: Mesh = bpy.data.meshes.new(self.path.stem)

        # create object
        self.object = bpy.data.objects.new(self.path.stem, self.mesh)

        # path to data folder
        material_folder = (self.path.with_suffix(self.path.suffix + "_data"))

        # path to material.xml file
        material_path = material_folder / "materials.xml"

        self.v_materials = parse_materials(material_path)

    def on_chunk_start(self, chunk: int, model: BufferedReader) -> None:
        if chunk == VChunkId.MTRS:
            self.process_mtrs(chunk, model)

        elif chunk == VChunkId.VMSH:
            self.process_vmsh(chunk, model)

        elif chunk == VChunkId.SKEL:
            self.process_skel(chunk, model)

        elif chunk == VChunkId.WGHT:
            self.process_wght(chunk, model)

        elif chunk == VChunkId.SUBM:
            self.process_subm(chunk, model)

    def process_mtrs(self, chunk: int, model: BufferedReader):
        def update_material(material: Material, token: str):
            path_length, = unpack("<i", model.read(4))
            assert path_length != 0

            path, = unpack("<%ss" % path_length, model.read(path_length))
            debug("useless path: %s", path)

            node_tree = material.node_tree
            nodes = node_tree.nodes

            v_material = self.v_materials.get(token)

            # TODO: use *.vmodel material
            if not v_material:
                error("MATERIAL NOT FOUND %s", token)
                return

            path = self.path.parent / v_material.diffuse

            if not path.exists():
                error("FILE NOT FOUND %s", path)
                return

            texture_node: ShaderNodeTexImage = nodes.new("ShaderNodeTexImage")
            texture_node.image = bpy.data.images.load(path.as_posix())
            l = texture_node.image.alpha_mode

            pbsdf_node = nodes.get("Principled BSDF")

            node_tree.links.new(
                pbsdf_node.inputs.get("Base Color"),
                texture_node.outputs.get("Color")
            )

            node_tree.links.new(
                pbsdf_node.inputs.get("Alpha"),
                texture_node.outputs.get("Alpha")
            )

            if token == 'MOB_ALPHA':
                material.blend_method = 'HASHED'
                material.shadow_method = 'HASHED'
            elif token == 'MOB_GLOW':
                emission_node: ShaderNodeEmission = nodes.new(
                    'ShaderNodeEmission'
                )

                emission_node.inputs.get('Strength').default_value = 3

                node_tree.links.new(
                    emission_node.inputs.get("Color"),
                    texture_node.outputs.get("Color")
                )

                add_shader_node: ShaderNodeAddShader = nodes.new(
                    'ShaderNodeAddShader'
                )

                node_tree.links.new(
                    add_shader_node.inputs[0],
                    pbsdf_node.outputs.get("BSDF")
                )

                node_tree.links.new(
                    add_shader_node.inputs[1],
                    emission_node.outputs.get("Emission")
                )

                material_output_node: ShaderNodeOutputMaterial = nodes.get(
                    'Material Output')

                node_tree.links.new(
                    material_output_node.inputs.get("Surface"),
                    add_shader_node.outputs.get("Shader")
                )

            debug("LOADED: %s", path)

        count, = unpack("<i", model.read(4))

        for _ in range(count):
            u1 = unpack("<i", model.read(4))

            chunk_name, = unpack("<I", model.read(4))

            u2, = unpack("<i", model.read(4))

            u3, = unpack("<H", model.read(2))

            mat_length, = unpack("<i", model.read(4))
            mat_name = unpack(
                "<%ss" % mat_length,
                model.read(mat_length))[0].decode("ASCII")

            material = bpy.data.materials.new(self.mesh.name + "_" + mat_name)
            self.mesh.materials.append(material)

            debug("mat_name: %s", mat_name)

            material.use_nodes = True

            model.seek(30, SEEK_CUR)

            update_material(material, mat_name)

            specular_length, = unpack("<i", model.read(4))
            assert specular_length == 0

            normalLength, = unpack("<i", model.read(4))
            assert normalLength == 0

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
            u13_name, = unpack(
                "<%ss" % u13_length,
                model.read(u13_length)
            )

            debug("u13_name: %s", u13_name)

            u14_length, = unpack("<i", model.read(4))
            u14_name, = unpack(
                "<%ss" % u14_length,
                model.read(u14_length)
            )

            debug("u14_name: %s", u14_name)

            u15_length, = unpack("<i", model.read(4))
            u15_name, = unpack(
                "<%ss" % u15_length,
                model.read(u15_length)
            )

            debug("u15_name: %s", u15_name)

            u16, u17, u18, u19, = unpack("<iiii", model.read(4 * 4))

            u19, = unpack("<i", model.read(4))

    def process_vmsh(self, chunk: int, model: BufferedReader):
        tell = model.tell()

        u1, u2, u3, u4 = unpack("<iiii", model.read(4 * 4))

        count = 15 * 4
        v = unpack(f"<{count}B", model.read(count))

        vertex_count, = unpack("<i", model.read(4))

        u5 = unpack(f"<{13}B", model.read(13))

        faces_count, = unpack("<i", model.read(4))

        model.seek(tell + 108)

        vertices = []
        uv_list = []
        for _ in range(vertex_count):
            t = model.tell()
            vx, vy, vz = unpack("<fff", model.read(12))
            vertices.append([vx, vy, vz])

            model.seek(t + v[16])
            tu, tv = unpack("<ff", model.read(8))
            uv_list.append([tu, tv])

            model.seek(t + v[8])

        count = faces_count * 3
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

        self.mesh.uv_layers.active = uv_layer

        # recalc normals
        self.mesh.calc_normals()

        # push changes
        self.mesh.update()

        self.context.collection.objects.link(self.object)

    def process_skel(self, chunk: int, model: BufferedReader):
        pass

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
