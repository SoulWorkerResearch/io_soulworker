from posixpath import normpath
import bpy

from bpy.types import Context, Operator, ShaderNodeTexImage
from bpy_extras.io_utils import ImportHelper

from io_soulworker.core.v_chunk_tag import VChunkTag
from io_soulworker.core.v_chunk_id import VChunkId
from io_soulworker.core.v_chunk_file import VChunkFile
from io_soulworker.core.utility import indices_to_face

from pathlib import Path
from struct import unpack
from logging import debug
from xml.dom import minidom
from os.path import basename, splitext, join
from io import BufferedReader, SEEK_CUR


class ImportModelHelper(Operator, ImportHelper):
    bl_idname = "import_model.helper"
    bl_label = "Select"

    def execute(self, context: Context):
        context.scene.render.engine = 'CYCLES'

        importer = ImportModel(self.properties.filepath, context)
        importer.run()

        return {'FINISHED'}


class ImportModel(VChunkFile):
    def __init__(self, path: str, context: Context) -> None:
        super(ImportModel, self).__init__(path)
        self.context = context
        self.mesh = bpy.data.meshes.new(self.path.name + "_mesh")

    def on_chunk_start(self, chunk: int, model: BufferedReader) -> None:
        vertices = []
        edges = []
        faces = []
        materials = []

        # print(x)
        if chunk == VChunkId.MTRS:
            count, = unpack("<i", model.read(4))

            for _ in range(count):
                u1 = unpack("<i", model.read(4))

                chunk_name, = unpack("<I", model.read(4))

                u2, = unpack("<i", model.read(4))

                u3, = unpack("<H", model.read(2))

                mat_length, = unpack("<i", model.read(4))
                mat_name, = unpack(
                    "<%ss" % mat_length,
                    model.read(mat_length)
                )

                mat_name_full = mat_name.decode('ASCII') + "_" + self.path.name

                material = bpy.data.materials.new(mat_name_full)
                self.mesh.materials.append(material)

                debug("mat_name: %s", mat_name)
                debug("mat_name_full: %s", mat_name_full)

                material.use_nodes = True

                model.seek(30, SEEK_CUR)

                diffuse_length, = unpack("<i", model.read(4))
                diffuse_path, = unpack(
                    "<%ss" % diffuse_length,
                    model.read(diffuse_length)
                )

                shader_name = "ShaderNodeTexImage"
                diffuse_texture: ShaderNodeTexImage = material.node_tree.nodes.new(
                    shader_name
                )

                diffuse_texture.image = bpy.data.images.load(
                    normpath(self.path.parent / diffuse_path.decode('ASCII'))
                )

                material.node_tree.links.new(
                    material.node_tree.nodes["Principled BSDF"].inputs['Base Color'],
                    diffuse_texture.outputs['Color']
                )

                debug("diffuse_path: %s", diffuse_path)

                specular_length, = unpack("<i", model.read(4))
                specular_name, = unpack(
                    "<%ss" % specular_length,
                    model.read(specular_length)
                )

                debug("specular_name: %s", specular_name)

                normal_length, = unpack("<i", model.read(4))
                normal_name, = unpack(
                    "<%ss" % normal_length,
                    model.read(normal_length)
                )

                debug("normal_name: %s", normal_name)

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

            for _ in range(vertex_count):
                t = model.tell()
                vx, vy, vz = unpack("<fff", model.read(12))
                vertices.append([vx, vy, vz])

                model.seek(t + v[16])
                tu, tv = unpack("<ff", model.read(8))

                model.seek(t + v[8])

            count = faces_count * 3
            indices = unpack(f"<{count}H", model.read(count * 2))
            faces = list(indices_to_face(indices))

            self.mesh.from_pydata(vertices, edges, faces)
            self.mesh.calc_normals()
            self.mesh.update()

            obj = bpy.data.objects.new(self.path.name, self.mesh)
            self.context.collection.objects.link(obj)

        elif chunk == VChunkId.SKEL:
            u1, u2, u3 = unpack("<iii", model.read(4 * 3))

            count,  = unpack("<i", model.read(4))

            for m in range(count):
                id_start, id_count, u6, u7, u8, u9, u10, u10 = unpack(
                    "<iiiiiiii",
                    model.read(4 * 8)
                )

                u11, u12, u13, u14, u15, u16 = unpack(
                    "<ffffff",
                    model.read(4 * 6)
                )

                materialId, count = unpack("<ii", model.read(4 * 2))

            pass

        elif chunk == VChunkId.WGHT:
            pass

        elif chunk == VChunkId.SUBM:
            pass
