from logging import debug
from logging import warn
from pathlib import Path
from xml.etree.ElementTree import Element, parse

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_stack_scope import VisChunkStackScope
from io_soulworker.core.vis_material_effect import VisMaterialEffect


class VisSurfaceChunk:

    def __init__(self, reader: BinaryReader) -> None:
        with VisChunkStackScope(reader) as scope:
            assert scope.cid == VisChunkId.MTRL

            version = reader.read_uint16()
            debug('version: %d', version)

            self.name = reader.read_utf8_uint32_string()
            debug("mat_name: %s", self.name)

            self.flags = reader.read_uint32()
            debug("flags: %s", repr(self.flags))

            self.ui_sorting_key = reader.read_uint32()
            """ internal sorting key; has to be in the range 0..15 """

            self.spec_mul = reader.read_float()
            """ Specular multiplier for material for the Vision engine """

            self.spec_exp = reader.read_float()
            """ Specular exponent for materials for the Vision engine """

            self.ui_transparency_type = reader.read_transparency()
            """ Transparency setting for materials in the Vision engine """

            self.ui_deferred_id = reader.read_uint8()
            """ material ID that is written to G-Buffer in deferred rendering """

            if version >= 3:
                self.depth_bias = reader.read_float()

            if version >= 4:
                self.depth_bias_clamp = reader.read_float()
                self.slope_scaled_depth_bias = reader.read_float()

            self.diffuse_map = reader.read_utf8_uint32_string()
            debug("diffuse path: %s", self.diffuse_map)

            self.specular_map = reader.read_utf8_uint32_string()
            debug("specular path: %s", self.specular_map)

            self.normal_map = reader.read_utf8_uint32_string()
            debug("normal path: %s", self.normal_map)

            if version >= 2:
                count = reader.read_uint32()
                aux_filenames = [reader.read_utf8_uint32_string(
                    reader) for _ in range(count)]

                for filename in aux_filenames:
                    debug("aux filename: %s", filename)

            self.user_data = reader.read_utf8_uint32_string()
            self.user_flags = reader.read_uint32()
            self.ambient_color = reader.read_color()
            reader.read_uint32()  # some unused (maybe colors)
            reader.read_uint32()  # some unused (maybe colors)
            self.parallax_scale = reader.read_float()
            self.parallax_bias = reader.read_float()
            self.config_effects = self.read_mesh_config_effects(reader)

            if version >= 5:
                self.override_library = reader.read_utf8_uint32_string()
                self.override_material = reader.read_utf8_uint32_string()

            if version >= 6:
                self.ui_mobile_shader_flags = reader.read_uint32()

    def read_mesh_config_effects(self, reader: BinaryReader) -> list[VisMaterialEffect]:
        count = reader.read_uint32()
        return [VisMaterialEffect(reader) for _ in range(count)]

    def load_material(self, path: Path) -> None:
        paths = self.__materials_paths__(path)
        for path in paths:
            debug('try load from: %s', path)
            if Path.exists(path):
                self.update_from_file(path)
                return

        warn("no materials.xml present")

    def update_from_file(self, path: Path) -> None:
        xml = parse(path).getroot()
        materialsNode = xml.find('./Materials')

        override = bool(materialsNode.get('override'))
        if override != True:
            return

        for material in materialsNode.iter('Material'):
            debug("name: %s", material.get('name'))
            pass

        # xml: Element = parse(path.as_posix())
        # xml.normalize()

        # root: Element = xml.getElementsByTagName("root")[0]
        # materials: Element = root.getElementsByTagName("Materials")[0]

        # def process(node: Element) -> list[str, VisMaterial]:
        #     material = VisMaterial()
        #     material.name = node.getAttribute("name")

        #     material.ambient = [int(v)
        #                         for v in node.getAttribute("ambient").split(',')]

        #     material.diffuse = node.getAttribute("diffuse")
        #     material.transparency = node.getAttribute("transparency")
        #     material.alphathreshold = float(
        #         node.getAttribute("alphathreshold"))

        #     return [material.name, material]

        # return dict(map(process, (node for node in materials.childNodes if node.nodeType == Node.ELEMENT_NODE)))

    def __materials_paths__(self, path: Path):
        # NPC_0001_Mirium.model -> NPC_0001_Mirium.model_data\\materials.xml
        yield path.parent / (path.name + "_data/materials.xml")

        # NPC_0001_Mirium.model -> Overrides\\NPC_0001_Mirium.model_data\\materials.xml
        yield path.parent / "Overrides" / (path.name + "_data/materials.xml")
