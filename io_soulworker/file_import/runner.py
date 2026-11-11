import bpy

from logging import debug, error
from pathlib import Path
from bpy_extras.io_utils import ImportHelper
from ..file_import.animation.file_reader import AnimationFileReader
from ..file_import.import_failure import report_import_failure
from ..file_import.model.file_reader import ModelFileReader
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    StringProperty,
)

from bpy.types import (
    Collection,
    Context,
    LayerCollection,
    Operator,
    OperatorFileListElement,
)


# https://github.com/microsoft/pylance-release/issues/5457#issuecomment-2074153709
def in_blender():

    return isinstance(bpy.app.version, tuple)


def operator_type_name(bl_idname: str) -> str:
    """Name under which a running operator reports its ``bl_idname``.

    ``"io_soulworker.import"`` reads ``"IO_SOULWORKER_OT_import"`` on the
    operator instance, such as the file browser's ``active_operator``.
    """

    module, _, name = bl_idname.partition(".")

    return f"{module.upper()}_OT_{name}"


def is_import_operator(operator) -> bool:
    """Whether ``operator`` (possibly ``None``) is a running SoulWorker import."""

    return (
        operator is not None
        and operator.bl_idname == operator_type_name(FileImportRunner.bl_idname)
    )


class FileImportRunner(Operator, ImportHelper):

    AVAILABLE_EXTENSIONS = [".model", ".vmesh", ".anim"]
    """Import SoulWorker model and animation files."""

    bl_idname = "io_soulworker.import"
    bl_label = "Select"

    # https://github.com/microsoft/pylance-release/issues/5457#issuecomment-2074153709
    if in_blender():

        is_create_collection: BoolProperty(
            name="Create collection",
            default=False,
        )  # type: ignore

        emission_strength: FloatProperty(
            name="Emission Strength",
            default=7,
            soft_min=0,
            min=0,
        )  # type: ignore

        # selected files
        files: CollectionProperty(type=OperatorFileListElement)  # type: ignore

        # the file browser lists only what this operator imports
        filter_glob: StringProperty(
            default="*.model;*.vmesh;*.anim",
            options={"HIDDEN"},
        )  # type: ignore

    else:

        is_create_collection: bool
        emission_strength: float
        files: list[OperatorFileListElement]
        filter_glob: str

    def draw(self, context):

        # Draws nothing: the file browser shows the options in the panels
        # ``FileImportObjectPanelDefaultValues`` and ``...Features``. Without
        # this method Blender would also list every property here.
        pass

    def create_collection(self, context: Context, name: str) -> Collection:

        def get_layer_collection(
                layer_collection: LayerCollection,
                collection: Collection):

            if (layer_collection.name == collection.name):

                return layer_collection

            for layer in layer_collection.children:

                found = get_layer_collection(layer, collection)

                if found:
                    return found

            raise Exception("No active layer")

        # collection for loaded object
        collection = bpy.data.collections.new(name)

        # link collection for user access
        context.collection.children.link(collection)

        view_layer = context.view_layer

        # get layer of linked collection
        layer_collection = view_layer.layer_collection

        # set created collection as active collection
        view_layer.active_layer_collection = get_layer_collection(
            layer_collection,
            collection
        )

        return collection

    def execute(self, context: Context):

        scene = context.scene
        view_layer = context.view_layer
        previous_engine = scene.render.engine
        previous_collection = view_layer.active_layer_collection

        scene.render.engine = "BLENDER_EEVEE"

        root = Path(self.properties.filepath)
        names = [file.name for file in self.files] or [root.name]
        collection = None

        if self.is_create_collection:

            collection = self.create_collection(context, root.parent.name)

        imported = 0

        for name in names:

            path: Path = root.parent / name

            if (
                not path.is_file()
                or path.suffix.lower() not in self.AVAILABLE_EXTENSIONS
            ):

                error("bad path, skipped: %s", path)
                self.report(
                    {"WARNING"},
                    f"Skipped {name}: not a .model, .vmesh or .anim file",
                )
                continue

            # One file that fails must not stop the ones after it.
            try:

                self._import_file(context, path)

            except Exception as failure:

                report_import_failure(self, path, failure)
                continue

            imported += 1

        if imported == 0:

            # Nothing came of it: give back what was changed beforehand.
            scene.render.engine = previous_engine

            if collection is not None:

                view_layer.active_layer_collection = previous_collection
                bpy.data.collections.remove(collection)

            return {"CANCELLED"}

        if imported < len(names):

            self.report(
                {"WARNING"},
                f"Imported {imported} of {len(names)} files; "
                "the others are listed as errors",
            )

        return {"FINISHED"}

    def _import_file(self, context: Context, path: Path) -> None:

        if path.suffix.lower() == ".anim":

            debug("import animation: %s", path)
            AnimationFileReader(
                path,
                context,
                report_warning=lambda msg: self.report({'WARNING'}, msg),
            ).run()

        else:

            debug("import model: %s", path)
            ModelFileReader(path, context, self.emission_strength).run()
