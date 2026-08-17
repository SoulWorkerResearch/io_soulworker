from logging import DEBUG, INFO, basicConfig, debug

import bpy

from io_soulworker.file_import.runner import FileImportRunner
from io_soulworker.file_import.object_panel_default_values import (
    FileImportObjectPanelDefaultValues,
)
from io_soulworker.file_import.object_panel_features import (
    FileImportObjectPanelFeatures,
)
from io_soulworker.file_export.operators import (
    IO_SOULWORKER_OT_export_model,
    IO_SOULWORKER_OT_export_vmesh,
)
from io_soulworker.viewport_resources_panel import (
    IO_SOULWORKER_OT_open_resource,
    IO_SOULWORKER_OT_open_scene,
    IO_SOULWORKER_PT_export,
    IO_SOULWORKER_PT_unpack_resources,
    register_unpack_resources_props,
    unregister_unpack_resources_props
)


basicConfig(
    level=DEBUG if __debug__ else INFO,
    format="[%(filename)40s():%(lineno)4s() - %(funcName)20s() ] %(message)s"
)

bl_info = {
    "name": "SoulWorker",
    "author": "sawich",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "File > Import/Export",
    "description": "Import-Export SoulWorker content",
    "support": "COMMUNITY",
    "category": "Import-Export",
}


classes = {
    FileImportObjectPanelDefaultValues,
    FileImportObjectPanelFeatures,
    FileImportRunner,
    IO_SOULWORKER_OT_open_resource,
    IO_SOULWORKER_OT_open_scene,
    IO_SOULWORKER_OT_export_vmesh,
    IO_SOULWORKER_OT_export_model,
    IO_SOULWORKER_PT_unpack_resources,
    IO_SOULWORKER_PT_export,
}


def menu_func_import(self, context):

    self.layout.operator(
        FileImportRunner.bl_idname,
        text="SoulWorker (.model, .vmesh, .anim)"
    )


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    register_unpack_resources_props()

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    unregister_unpack_resources_props()

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            debug('Failed to unload class: %s', cls.__name__)


if __name__ == "__main__":

    register()

# https://youtu.be/SdxsT40DaCg
