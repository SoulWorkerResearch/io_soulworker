import bpy
from bpy.props import StringProperty
from bpy.types import Context, Operator
from bpy_extras.io_utils import ImportHelper

from io_soulworker.core.v_chunk_tag import VChunkTag
from io_soulworker.core.v_chunk_id import VChunkId
from io_soulworker.core.v_chunk_file import VChunkFile
from io_soulworker.core.utility import indices_to_face

from os.path import basename, splitext
from io import BufferedReader, SEEK_CUR
from struct import unpack
from logging import debug


class ImportModelHelper(Operator, ImportHelper):
    bl_idname = "import_model.helper"
    bl_label = "Select"

    def execute(self, context: Context):
        importer = ImportModel(self.properties.filepath, context)
        importer.run()

        return {'FINISHED'}


class ImportModel(VChunkFile):
    def __init__(self, path: str, context: Context) -> None:
        super(ImportModel, self).__init__(path)
        self.context = context

    def on_chunk_start(self, chunk: int, model: BufferedReader) -> None:
        vertices = []
        edges = []
        faces = []

        # print(x)
        if chunk == VChunkId.MTRS:
            count, = unpack("<i", model.read(4))

            for material in range(count):
                u1 = unpack("<i", model.read(4))

                chunk_name, = unpack("<I", model.read(4))

                u2, = unpack("<i", model.read(4))

                u3, = unpack("<H", model.read(2))

                mat_length, = unpack("<i", model.read(4))
                mat_name, = unpack(
                    "<%ss" % mat_length,
                    model.read(mat_length)
                )

                debug("mat_name: %s", mat_name)

                model.seek(30, SEEK_CUR)

                diffuse_length, = unpack("<i", model.read(4))
                diffuse_name, = unpack(
                    "<%ss" % diffuse_length,
                    model.read(diffuse_length)
                )

                debug("diffuse_name: %s", diffuse_name)

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

                u6, = unpack("<i", model.read(4))
                u7, = unpack("<i", model.read(4))
                u8, = unpack("<i", model.read(4))
                u9, = unpack("<i", model.read(4))

                u10, = unpack("<i", model.read(4))
                u11, = unpack("<i", model.read(4))
                u12, = unpack("<i", model.read(4))

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

                u16, = unpack("<i", model.read(4))
                u17, = unpack("<i", model.read(4))
                u18, = unpack("<i", model.read(4))
                u19, = unpack("<i", model.read(4))

                u19, = unpack("<i", model.read(4))

        elif chunk == VChunkId.VMSH:
            tell = model.tell()

            u1, = unpack("<i", model.read(4))
            u2, = unpack("<i", model.read(4))
            u3, = unpack("<f", model.read(4))
            u4, = unpack("<i", model.read(4))

            count = 15 * 4
            v = unpack(f"<{count}B", model.read(count))

            vertex_count, = unpack("<i", model.read(4))

            u5 = unpack(f"<{13}B", model.read(13))

            faces_count, = unpack("<i", model.read(4))

            model.seek(tell + 108)

            for mesh in range(vertex_count):
                t = model.tell()
                vx, vy, vz = unpack("<fff", model.read(12))
                vertices.append([vx, vy, vz])

                model.seek(t + v[16])
                tu, tv = unpack("<ff", model.read(8))

                model.seek(t + v[8])

            count = faces_count * 3
            indices = unpack(f"<{count}H", model.read(count * 2))
            faces = list(indices_to_face(indices))

            filename, _ = splitext(basename(self.path))

            mesh = bpy.data.meshes.new(filename + "_mesh")
            mesh.from_pydata(vertices, edges, faces)
            mesh.update()

            obj = bpy.data.objects.new(filename, mesh)
            self.context.collection.objects.link(obj)

        elif chunk == VChunkId.SKEL:
            pass

        elif chunk == VChunkId.WGHT:
            pass

        elif chunk == VChunkId.SUBM:
            pass
