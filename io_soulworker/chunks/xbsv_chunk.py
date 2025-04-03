from io_soulworker.chunks.xbsv_frame import XbsvFrame
from io_soulworker.core.binary_reader import BinaryReader


class XbsvChunk:

    frame_count: int
    frame_list: list[XbsvFrame]

    def __init__(self, reader: BinaryReader) -> None:

        self.frame_count = reader.read_uint32()
        self.frame_list = [XbsvFrame(reader) for _ in range(self.frame_count)]
