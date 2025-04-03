from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_bounding_box import VisBoundingBox


class XbsvFrame:

    duration: float
    box: VisBoundingBox

    def __init__(self, reader: BinaryReader) -> None:

        self.duration = reader.read_float()
        self.box = reader.read_bounding_box()
