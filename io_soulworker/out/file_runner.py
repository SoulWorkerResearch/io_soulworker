from logging import error
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

from io_soulworker.out.model_importer import ModelImporter


class FileRunner(Operator, ImportHelper):
    bl_idname = "io_soulworker.import"
    bl_label = "Select"

    is_create_collection: BoolProperty(
        name="Create collection",
        default=False,
    )

    emission_strength: FloatProperty(
        name="Emission Strength",
        default=7,
        soft_min=0,
        min=0,
    )

    # selected files
    files: CollectionProperty(type=OperatorFileListElement)

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

    AVAILABLE_EXTENSIONS = [".model", ".vmesh"]

    def execute(self, context: Context):
        context.scene.render.engine = "BLENDER_EEVEE"

        root = Path(self.properties.filepath)

        if self.is_create_collection:
            self.create_collection(context, root.parent.name)

        for file in self.files:
            path: Path = root.parent / file.name
            ext = path.suffix.lower()

            if not path.is_file() or ext not in self.AVAILABLE_EXTENSIONS:
                error("bad path, skipped: %s", path)
                continue

            importer = ModelImporter(path, context, self.emission_strength)
            importer.run()

        return {"FINISHED"}
