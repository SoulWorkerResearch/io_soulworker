from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl
from io_soulworker.core.vis_bounding_box import HavokBoundingBox


class XbsvFrame(DataExchange_cl):

    duration = 0.0
    box = HavokBoundingBox()

    def read(self, reader: BinaryReader) -> None:

        self.duration = reader.read_float()
        self.box.read(reader)

    def write(self, writer: BinaryWriter) -> None:

        writer.write_float(self.duration)
        self.box.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'XbsvFrame':

        value = XbsvFrame()
        value.read(reader)

        return value
