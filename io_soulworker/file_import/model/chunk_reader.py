
from logging import debug, error, info
from pathlib import Path
from xml.etree.ElementTree import Element, ParseError, parse

from io_soulworker.chunks.bbbx_chunk import BBBXChunk
from io_soulworker.chunks.bnds_chunk import BNDSChunk
from io_soulworker.chunks.cbpr_chunk import CBPRChunk
from io_soulworker.chunks.expr_chunk import ExprChunk
from io_soulworker.chunks.mtrs_chunk import MtrsChunk
from io_soulworker.chunks.readers.wght_reader import WGHTChunkReader
from io_soulworker.chunks.skel_chunk import VisSkeletonChunk_cl
from io_soulworker.chunks.subm_chunk import VisSubMeshChunk
from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.materials_xml.shader_tag import ShaderTag
from io_soulworker.core.vis_chunk_file import VisChunkFileReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_reader_scope import VisChunkReaderScope
from io_soulworker.core.vis_material import VisMaterial
from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.core.xml_helper.exchange_transparency import exchange_transparency


class ModelChunkReader(VisChunkFileReader):

    xml_materials: dict[str, VisMaterial]

    def __init__(self, path: Path) -> None:

        super().__init__(path)

        self.xml_materials = {}

    def on_surface(self, chunk: MtrsChunk):
        debug('Not impl callback')

    def on_mesh(self, chunk: VMshChunk):
        debug('Not impl callback')

    def on_skeleton(self, chunk: VisSkeletonChunk_cl):
        debug('Not impl callback')

    def on_bounding_boxes(self, chunk: BBBXChunk):
        debug('Not impl callback')

    def on_skeleton_weights(self, reader: WGHTChunkReader):
        debug('Not impl callback')

    def on_sub_mesh(self, chunk: VisSubMeshChunk):
        debug('Not impl callback')

    def on_bnds(self, chunk: BNDSChunk):
        debug('Not impl callback')

    def on_cbpr(self, chunk: CBPRChunk):
        debug('Not impl callback')

    def on_export_transform(self, chunk: ExprChunk):
        debug('Not impl callback')

    def on_chunk_start(self, scope: VisChunkReaderScope, reader: BinaryReader) -> None:

        info('read chunk: %s', VisChunkId.get_name(scope.chunk))

        match scope.chunk:
            case VisChunkId.MTRS:
                self.__parse_materials(reader)

            case VisChunkId.VMSH:
                self.on_mesh(VMshChunk.from_reader(scope.chunk, reader))

            case VisChunkId.SKEL:
                self.on_skeleton(VisSkeletonChunk_cl.from_reader(reader))

            case VisChunkId.WGHT:
                self.on_skeleton_weights(WGHTChunkReader.from_reader(reader))

            case VisChunkId.SUBM:
                self.on_sub_mesh(VisSubMeshChunk.from_reader(reader))

            case VisChunkId.BBBX:
                self.on_bounding_boxes(BBBXChunk.from_reader(reader))

            case VisChunkId.BNDS:
                self.on_bnds(BNDSChunk.from_reader(reader))

            case VisChunkId.CBPR:
                self.on_cbpr(CBPRChunk.from_reader(reader))

            case VisChunkId.EXPR:
                self.on_export_transform(ExprChunk.from_reader(reader))

            case _:
                debug('Not impl callback: %s', scope.chunk)

    def __parse_materials(self, reader: BinaryReader) -> None:

        self.xml_materials = ModelChunkReader.__xml_material(reader)

        count = reader.read_uint32()

        for _ in range(count):
            chunk = MtrsChunk.from_reader(reader)

            override = self.xml_materials.get(chunk.name)
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

        debug('load materials from: %s', path)

        def __float(name: str, node: Element):
            return float(node.attrib[name])

        def __color(name: str, node: Element):
            return [int(v) for v in node.attrib[name].split(',')]

        def create(node: Element) -> tuple[str, VisMaterial]:
            material = VisMaterial()
            material.name = node.attrib["name"]

            shader_node = node.find('Shader')

            if shader_node is not None:
                material.shader = ShaderTag(shader_node)

            material.ambient = __color("ambient", node)

            material.diffuse = node.attrib["diffuse"]
            material.transparency = VisTransparencyType(
                exchange_transparency(node.attrib["transparency"])
            )

            material.alphathreshold = __float("alphathreshold", node)

            return (material.name, material)

        try:
            xml = parse(path)
        except ParseError as exc:
            error("Ignoring invalid materials.xml %s: %s", path, exc)
            return {}

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
