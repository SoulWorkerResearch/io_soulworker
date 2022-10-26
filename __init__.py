import bpy

from logging import basicConfig, debug
from logging import DEBUG, INFO

from io_soulworker.out.object_panel_default_values import OutObjectPanelDefaultValues
from io_soulworker.out.object_panel_features import OutObjectPanelFeatures
from io_soulworker.out.object_runner import ImportObjectRunner


basicConfig(
    level=DEBUG if __debug__ else INFO,
    format="[%(filename)40s():%(lineno)4s() - %(funcName)20s() ] %(message)s"
)


bl_info = {
    "name": "SoulWorker",
    "author": "sawich",
    "version": (1, 0, 0),
    "blender": (3, 4, 0),
    "location": "File > Import/Export",
    "description": "Import-Export SoulWorker content",
    "support": "COMMUNITY",
    "category": "Import-Export",
}


classes = {
    OutObjectPanelDefaultValues,
    OutObjectPanelFeatures,
    ImportObjectRunner,
}


def menu_func_import(self, context):
    self.layout.operator(
        ImportObjectRunner.bl_idname,
        text="SoulWorker (.model, .vmesh)"
    )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

# https://youtu.be/SdxsT40DaCg
