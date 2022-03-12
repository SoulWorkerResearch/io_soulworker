from struct import unpack
from logging import debug, warn
from io import BufferedReader
from xml.dom.minidom import Element, parse


from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.utility import read_color, read_mesh_config_effects, read_string
from io_soulworker.core.vis_surface_flags import VisSurfaceFlags
from io_soulworker.core.vis_transparency_type import VisTransparencyType


class MtrlChunk:
    def __init__(self, reader: BufferedReader, path: str) -> None:
        u1, = unpack("<I", reader.read(4))
        assert u1 == 1

        chunk_name, = unpack("<i", reader.read(4))
        assert chunk_name == VisChunkId.MTRL

        _, = unpack("<I", reader.read(4))

        v23, = unpack("<H", reader.read(2))

        self.name = read_string(reader)
        debug("mat_name: %s", self.name)

        # casted to VisSurfaceFlags (combinable)
        self.flags: VisSurfaceFlags = unpack("<I", reader.read(4))[0]

        # internal sorting key; has to be in the range 0..15
        self.ui_sorting_key, = unpack("<I", reader.read(4))

        # specular multiplier
        self.spec_mul, = unpack("<f", reader.read(4))

        # specular exponent
        self.spec_exp, = unpack("<f", reader.read(4))

        # casted to VisTransparencyType
        self.ui_transparency_type: VisTransparencyType = unpack("<B", reader.read(1))[
            0]

        # material ID that is written to G-Buffer in deferred rendering
        self.ui_deferred_id, = unpack("<B", reader.read(1))

        if v23 >= 3:
            self.depth_bias, = unpack("<f", reader.read(4))

        if v23 >= 4:
            self.depth_bias_clamp, = unpack("<f", reader.read(4))
            self.slope_scaled_depth_bias, = unpack("<f", reader.read(4))

        self.diffuse_map = read_string(reader)
        debug("inner diffuse path: %s", self.diffuse_map)

        self.specular_map = read_string(reader)
        debug("inner specular path: %s", self.specular_map)

        self.normal_map = read_string(reader)
        debug("inner normal path: %s", self.normal_map)

        if v23 >= 2:
            count, = unpack("<I", reader.read(4))
            aux_filenames = [read_string(reader) for _ in range(count)]

            for filename in aux_filenames:
                debug("aux filename: %s", filename)

        self.user_data = read_string(reader)
        self.user_flags, = unpack("<I", reader.read(4))
        self.ambient_color = read_color(reader)
        _, = unpack("<I", reader.read(4))
        _, = unpack("<I", reader.read(4))
        self.parallax_scale, = unpack("<f", reader.read(4))
        self.parallax_bias, = unpack("<f", reader.read(4))
        self.config_effects = read_mesh_config_effects(reader)

        if v23 >= 5:
            self.override_library = read_string(reader)
            self.override_material = read_string(reader)

        if v23 >= 6:
            self.ui_mobile_shader_flags, = unpack("<I", reader.read(4))

        u1, = unpack("<I", reader.read(4))
        assert u1 == 1

        chunk_name, = unpack("<I", reader.read(4))
        assert chunk_name == VisChunkId.MTRL

        self.__update_from_xml(reader)

    def __update_from_xml(self, root_path: str):
        pass
        # # path to data folder
        # material_folder = (root_path.with_suffix(root_path.suffix + "_data"))

        # # path to material.xml file
        # path = material_folder / "materials.xml"

        # if not root_path.exists():
        #     warn("no materials.xml present")
        #     return

        # xml: Element = parse(root_path.as_posix())
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
        #     material.alphathreshold = float(node.getAttribute("alphathreshold"))

        #     return [material.name, material]

        # return dict(map(process, (node for node in materials.childNodes if node.nodeType == Node.ELEMENT_NODE)))
