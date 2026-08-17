from logging import debug
from io_soulworker.chunks.atdm_chunk import AtdmChunk
from io_soulworker.chunks.atdo_chunk import AtdoChunk
from io_soulworker.chunks.atdr_chunk import AtdrChunk
from io_soulworker.chunks.bpos_chunk import BposChunk
from io_soulworker.chunks.brot_chunk import BrotChunk
from io_soulworker.chunks.bscl_chunk import BsclChunk
from io_soulworker.chunks.xbsv_chunk import XbsvChunk
from io_soulworker.chunks.head_chunk import HeadChunk
from io_soulworker.chunks.skel_chunk import VisSkeletonChunk_cl
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

    def on_bone_scale(self, chunk: BsclChunk) -> None:
        debug('Not impl callback')

    def on_offset_delta(self, chunk: AtdoChunk) -> None:
        debug('Not impl callback')

    def on_rotation_delta(self, chunk: AtdrChunk) -> None:
        debug('Not impl callback')

    def on_motion_delta(self, chunk: AtdmChunk) -> None:
        debug('Not impl callback')

    def on_animation(self, skeleton_index: int, name: str) -> None:
        debug('Not impl callback')

    def on_animation_end(self) -> None:
        debug('Not impl callback')

    def on_skeleton(self, chunk: VisSkeletonChunk_cl) -> None:
        debug('Not impl callback')

    def on_chunk_start(
            self,
            scope: VisChunkReaderScope,
            reader: BinaryReader) -> None:

        if scope.chunk == VisChunkId.HEAD:

            head = HeadChunk.from_reader(reader)

            self.sequence_count = head.sequence_count

        elif scope.chunk == VisChunkId.BANI:

            version = reader.read_uint16()
            debug("version: %d", version)

            skeleton_index = reader.read_uint16()
            debug("skeleton_index: %d", skeleton_index)

            self.bone_count = reader.read_uint16()
            debug("bone_count: %d", self.bone_count)

            name = reader.read_utf8_uint32_string()
            debug("name: %s", name)

            self.on_animation(skeleton_index, name)
            self.run_sub(reader, scope)
            self.on_animation_end()

        elif scope.chunk == VisChunkId.SKEL:

            self.on_skeleton(VisSkeletonChunk_cl.from_reader(reader))

        elif scope.chunk == VisChunkId.VSBX:

            self.on_visability_bounding_box(XbsvChunk.from_reader(reader))

        elif scope.chunk == VisChunkId.BPOS:

            self.on_bone_position(
                BposChunk.from_reader(reader, self.bone_count)
            )

        elif scope.chunk == VisChunkId.BROT:

            self.on_bone_rotation(
                BrotChunk.from_reader(reader, self.bone_count)
            )

        elif scope.chunk == VisChunkId.BSCL:

            self.on_bone_scale(
                BsclChunk.from_reader(reader, self.bone_count)
            )

        elif scope.chunk == VisChunkId.ATDO:

            self.on_offset_delta(AtdoChunk.from_reader(reader))

        elif scope.chunk == VisChunkId.ATDR:

            self.on_rotation_delta(AtdrChunk.from_reader(reader))

        elif scope.chunk == VisChunkId.ATDM:

            self.on_motion_delta(AtdmChunk.from_reader(reader))

        elif scope.chunk == VisChunkId.ANIM:

            version = reader.read_uint16()

            self.run_sub(reader, scope)
