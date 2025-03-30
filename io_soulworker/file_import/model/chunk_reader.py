
from logging import debug
from pathlib import Path
from xml.etree.ElementTree import Element, parse

from io_soulworker.chunks.bbbx_chunk import BBBXChunk
from io_soulworker.chunks.bnds_chunk import BNDSChunk
from io_soulworker.chunks.cbpr_chunk import CBPRChunk
from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.readers.wght_reader import WGHTChunkReader
from io_soulworker.chunks.skel_chunk import SkelChunk
from io_soulworker.chunks.subm_chunk import SubmChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.materials_xml.shader_tag import ShaderTag
from io_soulworker.core.vis_chunk_file import VisChunkFileReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_material import VisMaterial
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.core.xml_helper.exchange_transparency import exchange_transparency


class ModelChunkReader(VisChunkFileReader):

    def on_surface(self, chunk: MtrsChunk):
        debug('Not impl callback')

    def on_mesh(self, chunk: VMshChunk):
        debug('Not impl callback')

    def on_skeleton(self, chunk: SkelChunk):
        debug('Not impl callback')

    def on_bounding_boxes(self, chunk: BBBXChunk):
        debug('Not impl callback')

    def on_skeleton_weights(self, reader: WGHTChunkReader):
        debug('Not impl callback')

    def on_vertices_material(self, chunk: SubmChunk):
        debug('Not impl callback')

    def on_bnds(self, chunk: BNDSChunk):
        debug('Not impl callback')

    def on_cbpr(self, chunk: CBPRChunk):
        debug('Not impl callback')

    def on_chunk_start(self, chunk: VisChunkId, reader: BinaryReader) -> None:

        if chunk == VisChunkId.MTRS:
            self.__parse_materials(reader)

        elif chunk == VisChunkId.VMSH:
            self.on_mesh(VMshChunk(chunk, reader))

        elif chunk == VisChunkId.SKEL:
            self.on_skeleton(SkelChunk(reader))

        elif chunk == VisChunkId.WGHT:
            self.on_skeleton_weights(WGHTChunkReader(reader))

        elif chunk == VisChunkId.SUBM:
            self.on_vertices_material(SubmChunk(reader))

        elif chunk == VisChunkId.BBBX:
            self.on_bounding_boxes(BBBXChunk(reader))

        elif chunk == VisChunkId.BNDS:

            self.on_bnds(BNDSChunk(reader))

        elif chunk == VisChunkId.CBPR:
            self.on_cbpr(CBPRChunk(reader))

    def __parse_materials(self, reader: BinaryReader):

        overrides = ModelChunkReader.__xml_material(reader)

        count = reader.read_uint32()

        for _ in range(count):
            chunk = MtrsChunk(reader)

            override = overrides.get(chunk.name)
            if override:
                chunk.diffuse_map = override.diffuse

            self.on_surface(chunk)

    @staticmethod
    def __xml_material(reader: BinaryReader) -> dict[str, VisMaterial]:

        paths = ModelChunkReader.__materials_paths(Path(reader.name))

        values = dict[str, VisMaterial]()

        for path in paths:
            debug('try load from: %s', path)

            if Path.exists(path):
                debug('load from: %s', path)
                values.update(ModelChunkReader.__material_from_file(path))

        return values

    @staticmethod
    def __material_from_file(path: Path) -> dict[str, VisMaterial]:

        def __float(name: str, node: Element):
            return float(node.attrib[name])

        def __color(name: str, node: Element):
            return [int(v) for v in node.attrib[name].split(',')]

        def create(node: Element) -> tuple[str, VisMaterial]:
            material = VisMaterial()
            material.name = node.attrib["name"]

            shader_node = node.find('Shader')
            if shader_node is not None:
                shader = ShaderTag(node.find('Shader'))

            material.ambient = __color("ambient", node)

            material.diffuse = node.attrib["diffuse"]
            material.transparency = VisTransparencyType(
                exchange_transparency(node.attrib["transparency"]))

            material.alphathreshold = __float("alphathreshold", node)

            return (material.name, material)

        xml = parse(path)
        root = xml.getroot()

        materials = root.find('Materials')
        if not isinstance(materials, Element):
            return dict()

        return dict(map(create, (node for node in materials.findall('Material'))))

    @staticmethod
    def __materials_paths(path: Path):

        file = Path(path.name + "_data", "materials.xml")

        # NPC_0001_Mirium.model -> NPC_0001_Mirium.model_data\\materials.xml
        yield path.parent / file

        # NPC_0001_Mirium.model -> Overrides\\NPC_0001_Mirium.model_data\\materials.xml
        yield path.parent / "Overrides" / file
