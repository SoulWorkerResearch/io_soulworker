from logging import DEBUG, INFO, basicConfig, debug

try:
    import bpy
except ModuleNotFoundError:
    bpy = None

if bpy is not None:
    from io_soulworker.file_import.runner import FileImportRunner
    from io_soulworker.file_import.object_panel_default_values import FileImportObjectPanelDefaultValues
    from io_soulworker.file_import.object_panel_features import FileImportObjectPanelFeatures

basicConfig(
    level=DEBUG if __debug__ else INFO,
    format="[%(filename)40s():%(lineno)4s() - %(funcName)20s() ] %(message)s"
)

bl_info = {
    "name": "SoulWorker",
    "author": "sawich",
    "version": (1, 0, 0),
    "blender": (5, 1, 1),
    "location": "File > Import/Export",
    "description": "Import-Export SoulWorker content",
    "support": "COMMUNITY",
    "category": "Import-Export",
}


classes = set()

if bpy is not None:
    classes = {
        FileImportObjectPanelDefaultValues,
        FileImportObjectPanelFeatures,
        FileImportRunner,
    }


def menu_func_import(self, context):
    if bpy is None:
        return

    self.layout.operator(
        FileImportRunner.bl_idname,
        text="SoulWorker (.model, .vmesh, .anim)"
    )


def register():
    if bpy is None:
        return

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    if bpy is None:
        return

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            debug('Failed to unload class: %s', cls.__name__)


if __name__ == "__main__":

    register()

# https://youtu.be/SdxsT40DaCg
