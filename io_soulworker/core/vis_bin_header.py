from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl
from io_soulworker.core.vis_chunk_id import VisChunkId


class VisBinHeader(DataExchange_cl):

    cid = VisChunkId.NONE
    version = 0

    def read(self, reader: BinaryReader) -> None:

        self.cid = reader.read_cid()
        self.version = reader.read_uint32()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_cid(self.cid)
        writer.write_uint32(self.version)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'VisBinHeader':

        value = VisBinHeader()
        value.read(reader)

        return value
