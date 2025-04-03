from logging import debug
from io_soulworker.chunks.bpos_chunk import BposChunk
from io_soulworker.chunks.brot_chunk import BrotChunk
from io_soulworker.chunks.xbsv_chunk import XbsvChunk
from io_soulworker.chunks.head_chunk import HeadChunk
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_file import VisChunkFileReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_reader_scope import VisChunkReaderScope


class AnimationFileChunkReader(VisChunkFileReader):

    sequence_count = 0
    bone_count = 0

    def on_visability_bounding_box(self, chunk: XbsvChunk) -> None:
        debug('Not impl callback')

    def on_bone_position(self, chunk: BposChunk) -> None:
        debug('Not impl callback')

    def on_bone_rotation(self, chunk: BrotChunk) -> None:
        debug('Not impl callback')

    def on_animation(self, skeleton_index: int, name: str) -> None:
        debug('Not impl callback')

    def on_chunk_start(self, scope: VisChunkReaderScope, reader: BinaryReader) -> None:

        if scope.chunk == VisChunkId.HEAD:

            head = HeadChunk(reader)

            self.sequence_count = head.sequence_count

        elif scope.chunk == VisChunkId.BANI:

            version = reader.read_uint16()
            skeleton_index = reader.read_uint16()
            self.bone_count = reader.read_uint16()
            name = reader.read_utf8_uint32_string()

            self.on_animation(skeleton_index, name)
            self.run_sub(reader, scope.length)

        elif scope.chunk == VisChunkId.XBSV:

            self.on_visability_bounding_box(XbsvChunk(reader))

        elif scope.chunk == VisChunkId.BPOS:

            self.on_bone_position(BposChunk(self.bone_count, reader))

        elif scope.chunk == VisChunkId.BROT:

            self.on_bone_rotation(BrotChunk(self.bone_count, reader))

        elif scope.chunk == VisChunkId.ANIM:

            version = reader.read_uint16()

            self.run_sub(reader, scope.length)
