
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_id import VisChunkId


class VisBinHeader:

    cid = VisChunkId.NONE
    version = 0

    def __init__(self, reader: BinaryReader) -> None:

        self.cid = reader.read_cid()
        self.version = reader.read_uint32()
