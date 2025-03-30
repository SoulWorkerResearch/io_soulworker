from io import BufferedWriter
from pathlib import Path
import struct
import bpy

from io_soulworker.core.vis_chunk_id import VisChunkId


class ChunkWriter:
    @staticmethod
    def writer(path: Path, context: bpy.types.Context) -> None:
        version = 3  # temp version

        with BinaryWriter(open(path, "wb")) as f:

            f.u32(len(context.active_object.material_slots))

            for material in context.active_object.material_slots:
                f.u32(1)  # stack depth
                f.u32(VisChunkId.MTRL)

                # chunk data
                f.u32(0)  # length
                data_start_offset = f.tell()

                f.u16(version)  # version

                f.u32_string(material.name)
                f.u32(0)  # flags

                if (version >= 9):
                    f.u8(0)  # lighting method

                f.u32(0)  # ui sorting key
                f.f32(0.0)  # spec_mul
                f.f32(0.0)  # spec_exp
                f.u8(0)  # transparency type
                f.u8(0)  # ui deferred id

                if version >= 3:
                    f.f32(0.0)  # depth bias

                if version >= 4:
                    f.f32(0.0)  # depth bias clamp
                    f.f32(0.0)  # slope scaled depth bias

                if version >= 7:
                    f.f32(0.0)  # custom alpha threshold

                f.u32_string("")  # duffuse texture
                f.u32_string("")  # specular texture
                f.u32_string("")  # normal texture

                if version >= 2:
                    aux_count = 0

                    f.u32(aux_count)  # auxiliary texture count

                    for _ in range(aux_count):
                        f.u32_string("")  # auxiliary texture

                f.u32_string("")  # user data
                f.u32(0)  # user flags
                f.color(0, 0, 0, 0)  # ambient color
                f.u32(0)  # brightness
                f.color(0, 0, 0, 0)  # light color
                f.f32(0.0)  # paralax scale
                f.f32(0.0)  # paralax bias

                config_effects_count = 0

                f.u32(config_effects_count)  # config effects count

                for _ in range(config_effects_count):
                    f.u32_string("")  # library
                    f.u32_string("")  # name
                    f.u32_string("")  # param

                if version >= 5:
                    f.u32_string("")  # override library
                    f.u32_string("")  # override material

                if version >= 6:
                    f.u32(0)  # ui mobile shader flag

                data_end_offset = f.tell()

                # move to begin of the chunk for overwrite data length
                # begin of the chunk - sizeof int
                f.seek(data_start_offset - 4)

                f.u32(data_end_offset - data_start_offset)  # data length

                f.seek(data_end_offset)

                # chunk tail
                f.u32(1)  # stack depth
                f.u32(VisChunkId.MTRL)


class BinaryWriter(BufferedWriter):
    def u32(self, value: int) -> None:
        self.write(struct.pack('<I', value))

    def u16(self, value: int) -> None:
        self.write(struct.pack('<H', value))

    def u8(self, value: int) -> None:
        self.write(struct.pack('<B', value))

    def f32(self, value: float) -> None:
        self.write(struct.pack('<f', value))

    def u32_string(self, string: str) -> None:
        l = len(string)
        self.write(struct.pack('<I%ds' % (l), l, string.encode('utf-8')))

    def color(self, r: int, g: int, b: int, a: int) -> None:
        self.write(struct.pack('<4B', r, g, b, a))


class SimpleOperator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.simple_operator"
    bl_label = "Simple Object Operator"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        print("execute SimpleOperator")

        path = Path(
            "Q:/Users/sawic/source/repos/SoulWorkerResearch/python/scripts/addons/blender-io_soulworker/tests/datas/Models/MagicBall.model_chunk/MTRS_export.bin")

        ChunkWriter.writer(path, context)

        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(
        SimpleOperator.bl_idname,
        text=SimpleOperator.bl_label
    )


def register():
    bpy.utils.register_class(SimpleOperator)

    # MenuBar "Object"
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    bpy.utils.unregister_class(SimpleOperator)

    # MenuBar "Object"
    bpy.types.VIEW3D_MT_object.remove(menu_func)
