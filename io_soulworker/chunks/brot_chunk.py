from io_soulworker.chunks.brot_chunk_key_frame import BrotChunk_KeyFrame
from io_soulworker.core.binary_reader import BinaryReader


class BrotChunk:

    key_frame_count: int
    key_frame_list: list[BrotChunk_KeyFrame]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.key_frame_count = reader.read_uint32()
        self.key_frame_list = [
            BrotChunk_KeyFrame(bone_count, reader) for _ in range(self.key_frame_count)
        ]
