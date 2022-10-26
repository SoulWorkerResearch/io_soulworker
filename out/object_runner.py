import bpy

from bpy.props import CollectionProperty
from bpy.props import FloatProperty
from bpy.props import BoolProperty
from bpy.types import Context
from bpy.types import LayerCollection
from bpy.types import Collection
from bpy.types import Operator
from bpy.types import PropertyGroup
from bpy_extras.io_utils import ImportHelper

from io_soulworker.out.model_importer import ModelImporter

from pathlib import Path
from logging import error


class ImportObjectRunner(Operator, ImportHelper):
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
    files: CollectionProperty(type=PropertyGroup)

    def draw(self, context):
        # disable draw standard controls
        pass

    def create_collection(self, context: Context, name: str):

        def get_layer_collection(layer_collection: LayerCollection, collection: Collection):
            found = None

            if (layer_collection.name == collection.name):
                return layer_collection

            for layer in layer_collection.children:
                found = get_layer_collection(layer, collection)

                if found:
                    return found

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
