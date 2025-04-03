from io_soulworker.chunks.bpos_chunk_key_frame import BposChunk_KeyFrame
from io_soulworker.core.binary_reader import BinaryReader


class BposChunk:

    key_frame_count: int
    key_frame_list: list[BposChunk_KeyFrame]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.key_frame_count = reader.read_uint32()

        self.key_frame_list = [
            BposChunk_KeyFrame(bone_count, reader) for _ in range(self.key_frame_count)
        ]
