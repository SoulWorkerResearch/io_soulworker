import bpy

from logging import basicConfig, DEBUG
from io_soulworker.sw_import.model import ImportModelRunner


basicConfig(
    level=DEBUG,
    format="[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
)


bl_info = {
    "name": "SoulWorker",
    "author": "sawich",
    "version": (1, 0, 0),
    "blender": (2, 92, 0),
    "location": "File > Import/Export",
    "description": "Import-Export SoulWorker content",
    "support": 'COMMUNITY',
    "category": "Import-Export",
}


classes = {
    ImportModelRunner
}


def menu_func_import(self, context):
    self.layout.operator(
        ImportModelRunner.bl_idname,
        text="SoulWorker (.model)"
    )


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for c in classes:
        bpy.utils.unregister_class(c)
