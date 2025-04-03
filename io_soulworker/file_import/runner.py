
from logging import debug, error
from pathlib import Path

import bpy

from bpy.props import BoolProperty, CollectionProperty, FloatProperty
from bpy.types import (
    Collection,
    Context,
    LayerCollection,
    Operator,
    OperatorFileListElement,
)

from bpy_extras.io_utils import ImportHelper

from io_soulworker.file_import.animation.file_reader import AnimationFileReader
from io_soulworker.file_import.model.file_reader import ModelFileReader


# https://github.com/microsoft/pylance-release/issues/5457#issuecomment-2074153709
def in_blender():
    return type(bpy.app.version) == tuple


class FileImportRunner(Operator, ImportHelper):

    AVAILABLE_EXTENSIONS = [".model", ".vmesh"]

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

    else:

        is_create_collection: bool
        emission_strength: float
        files: list[OperatorFileListElement]

    def draw_menu(self, context):
        # disable draw standard controls
        pass

    def create_collection(self, context: Context, name: str):

        def get_layer_collection(layer_collection: LayerCollection, collection: Collection):

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

    def execute(self, context: Context):
        context.scene.render.engine = "BLENDER_EEVEE_NEXT"

        root = Path(self.properties.filepath)

        if self.is_create_collection:

            self.create_collection(context, root.parent.name)

        for file in self.files:

            path: Path = root.parent / file.name
            ext = path.suffix.lower()

            if not path.is_file() or ext not in self.AVAILABLE_EXTENSIONS:

                error("bad path, skipped: %s", path)
                continue

            # ModelFileReader(path, context, self.emission_strength).run()

            path = path.with_suffix(".anim")

            if path.is_file():

                debug("animation path: %s", path)
                AnimationFileReader(path, context).run()

        return {"FINISHED"}
