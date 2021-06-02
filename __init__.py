import bpy

from io_soulworker.sw_import.object_panel_default_values import ImportObjectPanelDefaultValues
from io_soulworker.sw_import.object_panel_features import ImportObjectPanelFeatures
from io_soulworker.sw_import.object_runner import ImportObjectRunner

from logging import basicConfig
from logging import DEBUG


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
    "support": "COMMUNITY",
    "category": "Import-Export",
}


classes = {
    ImportObjectPanelDefaultValues,
    ImportObjectPanelFeatures,
    ImportObjectRunner,
}


def menu_func_import(self: bpy.types.TOPBAR_MT_file_import, context):
    self.layout.operator(
        ImportObjectRunner.bl_idname,
        text="SoulWorker (.model)"
    )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in classes:
        bpy.utils.unregister_class(cls)


# https://youtu.be/SdxsT40DaCg
