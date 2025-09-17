from io_soulworker.chunks.xbsv_frame import XbsvFrame
from io_soulworker.core.binary_reader import BinaryReader


class XbsvChunk:

    frame_list: list[XbsvFrame]

    def __init__(self, reader: BinaryReader) -> None:

        frame_count = reader.read_uint32()
        assert frame_count > 0

        self.frame_list = [XbsvFrame(reader) for _ in range(frame_count)]
