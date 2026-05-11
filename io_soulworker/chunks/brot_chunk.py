from io_soulworker.chunks.brot_chunk_key_frame import BrotChunk_KeyFrame
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class BrotChunk(DataExchange_cl):

    bone_count = 0
    key_frame_list: list[BrotChunk_KeyFrame]

    def __init__(self) -> None:

        self.key_frame_list = []

    def read(self, reader: BinaryReader) -> None:

        key_frame_count = reader.read_uint32()
        assert key_frame_count > 0

        self.key_frame_list = [
            BrotChunk_KeyFrame.from_reader(reader, self.bone_count) for _ in range(key_frame_count)
        ]

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(len(self.key_frame_list))

        for key_frame in self.key_frame_list:
            key_frame.write(writer)

    @staticmethod
    def from_reader(reader: BinaryReader, bone_count: int) -> 'BrotChunk':

        value = BrotChunk()
        value.bone_count = bone_count
        value.read(reader)

        return value
