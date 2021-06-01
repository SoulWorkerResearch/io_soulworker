import bpy
from bpy import context

from bpy.types import Context, Material, Mesh, MeshFaceMap, MeshFaceMapLayer, MeshVertex, Object, Operator, ShaderNodeTexImage
from bpy_extras.io_utils import ImportHelper

from io_soulworker.core.v_chunk_tag import VChunkTag
from io_soulworker.core.v_chunk_id import VChunkId
from io_soulworker.core.v_chunk_file import VChunkFile
from io_soulworker.core.utility import indices_to_face

from enum import Enum
from struct import unpack
from logging import debug
from xml.dom import minidom
from posixpath import normpath
from io import BufferedReader, SEEK_CUR


class ImportModelHelper(Operator, ImportHelper):
    bl_idname = "import_model.helper"
    bl_label = "Select"

    def execute(self, context: Context):
        context.scene.render.engine = 'BLENDER_EEVEE'

        importer = ImportModel(self.properties.filepath, context)
        importer.run()

        return {'FINISHED'}


class VTextureType(Enum):
    BASE_COLOR = "Base Color"
    SPECULAR = "Specular"
    NORMAL = "Normal"


class ImportModel(VChunkFile):
    mesh: Mesh = None
    object: Object = None

    def __init__(self, path: str, context: Context) -> None:
        super(ImportModel, self).__init__(path)

        # save context
        self.context = context

        # create emesh
        self.mesh: Mesh = bpy.data.meshes.new(self.path.name + "_mesh")

        # create object
        self.obj = bpy.data.objects.new(self.path.name, self.mesh)

    def updateMaterial(self, model: BufferedReader, material: Material, type: VTextureType):
        path_length, = unpack("<i", model.read(4))
        if (path_length > 0):
            path, = unpack("<%ss" % path_length, model.read(path_length))

            node_tree = material.node_tree
            nodes = node_tree.nodes

            texture_node: ShaderNodeTexImage = nodes.new("ShaderNodeTexImage")

            path = normpath(self.path.parent / path.decode('ASCII'))
            texture_node.image = bpy.data.images.load(path)

            input = nodes.get("Principled BSDF").inputs.get(type.value)
            output = texture_node.outputs.get('Color')

            node_tree.links.new(input, output)

            debug("%s: %s", type.value, path)
        else:
            debug("UNUSED %s", type.value)

    def on_chunk_start(self, chunk: int, model: BufferedReader) -> None:
        if chunk == VChunkId.MTRS:
            count, = unpack("<i", model.read(4))

            for _ in range(count):
                u1 = unpack("<i", model.read(4))

                chunk_name, = unpack("<I", model.read(4))

                u2, = unpack("<i", model.read(4))

                u3, = unpack("<H", model.read(2))

                mat_length, = unpack("<i", model.read(4))
                mat_name, = unpack("<%ss" % mat_length, model.read(mat_length))

                mat_name_full = mat_name.decode('ASCII') + "_" + self.path.stem

                material = bpy.data.materials.new(mat_name_full)
                self.mesh.materials.append(material)

                debug("mat_name: %s", mat_name)
                debug("mat_name_full: %s", mat_name_full)

                material.use_nodes = True

                model.seek(30, SEEK_CUR)

                self.updateMaterial(model, material, VTextureType.BASE_COLOR)
                self.updateMaterial(model, material, VTextureType.SPECULAR)
                self.updateMaterial(model, material, VTextureType.NORMAL)

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

        elif chunk == VChunkId.VMSH:
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
                        1 - uv_list[vert_idx][1]
                    ]

            self.mesh.uv_layers.active = uv_layer

            # recalc normals
            self.mesh.calc_normals()

            # push changes
            self.mesh.update()

            self.context.collection.objects.link(self.obj)

        elif chunk == VChunkId.SKEL:
            pass

        elif chunk == VChunkId.WGHT:
            pass

        elif chunk == VChunkId.SUBM:
            u1, u2, u3 = unpack("<iii", model.read(4 * 3))

            count, = unpack("<i", model.read(4))

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

                material_name = self.mesh.materials[material_id].name_full
                vertex_group = self.obj.vertex_groups.new(name=material_name)

                indices = self.indices[indices_start:indices_start + indices_count]
                vertex_group.add(indices, 1, 'REPLACE')

                debug("material_id: %d", material_id)
                debug("indices_start: %d", indices_start)
                debug("indices_count: %d", indices_count)
