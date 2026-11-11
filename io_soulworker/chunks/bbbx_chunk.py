from ..core.binary_reader import BinaryReader
from ..core.binary_writer import BinaryWriter
from ..core.data_exchange import DataExchange_cl
from ..core.vis_bounding_box import HavokBoundingBox


class BBBXChunk(DataExchange_cl):

    class Entity(DataExchange_cl):

        bounds: HavokBoundingBox

        def __init__(self) -> None:

            self.bounds = HavokBoundingBox()

        def read(self, reader: BinaryReader) -> None:

            self.bounds.read(reader)

        def write(self, writer: BinaryWriter) -> None:

            self.bounds.write(writer)

        @staticmethod
        def from_reader(reader: BinaryReader) -> 'BBBXChunk.Entity':

            value = BBBXChunk.Entity()
            value.read(reader)

            return value

    values: list['BBBXChunk.Entity']

    def __init__(self) -> None:

        self.values = []

    def read(self, reader: BinaryReader) -> None:

        count = reader.read_uint16()
        self.values = [BBBXChunk.Entity.from_reader(
            reader) for _ in range(count)]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint16(len(self.values))

        for entity in self.values:
            entity.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'BBBXChunk':

        value = BBBXChunk()
        value.read(reader)

        return value
