from io_soulworker.chunks.xbsv_frame import XbsvFrame
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class XbsvChunk(DataExchange_cl):

    frame_list: list[XbsvFrame]

    def __init__(self) -> None:

        self.frame_list = []

    def read(self, reader: BinaryReader) -> None:

        frame_count = reader.read_uint32()
        assert frame_count > 0

        self.frame_list = [
            XbsvFrame.from_reader(reader)
            for _ in range(frame_count)
        ]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(len(self.frame_list))

        for frame in self.frame_list:

            frame.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'XbsvChunk':

        value = XbsvChunk()
        value.read(reader)

        return value
