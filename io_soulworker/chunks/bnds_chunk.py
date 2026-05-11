from mathutils import Vector

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl
from io_soulworker.core.vis_bounding_box import HavokBoundingBox


class BNDSChunk(DataExchange_cl):

    bounding_box = HavokBoundingBox()
    bounding_sphere_radius = Vector()
    collision_bounding_box = HavokBoundingBox()

    def read(self, reader: BinaryReader) -> None:

        self.bounding_box.read(reader)
        self.bounding_sphere_radius = reader.read_vector4()
        self.collision_bounding_box.read(reader)

    def write(self, writer: BinaryWriter) -> None:

        self.bounding_box.write(writer)
        writer.write_vector4(self.bounding_sphere_radius)
        self.collision_bounding_box.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'BNDSChunk':

        value = BNDSChunk()
        value.read(reader)

        return value
