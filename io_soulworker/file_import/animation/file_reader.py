import bpy

from logging import debug
from mathutils import Quaternion, Vector
from pathlib import Path
from io_soulworker.chunks.head_chunk import HeadChunk
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_file import VisChunkFileReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_reader_scope import VisChunkReaderScope


class VisBoundingBox:

    min: Vector
    max: Vector


class XbsvFrame:

    duration: float
    box: VisBoundingBox

    def __init__(self, reader: BinaryReader) -> None:

        self.duration = reader.read_float()
        self.box = reader.read_bounding_box()


class XbsvChunk:

    frame_count: int
    frame_list: list[XbsvFrame]

    def __init__(self, reader: BinaryReader) -> None:

        self.frame_count = reader.read_uint32()
        self.frame_list = [XbsvFrame(reader) for _ in range(self.frame_count)]


class BposChunk_KeyFrame:

    time: float
    vector_list: list[Vector]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.time = reader.read_float()

        self.vector_list = [
            reader.read_float_vector3() for _ in range(bone_count)
        ]

        for i in range(bone_count):

            self.vector_list[i].w = 1.0


class BposChunk:

    key_frame_count: int
    key_frame_list: list[BposChunk_KeyFrame]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.key_frame_count = reader.read_uint32()

        self.key_frame_list = [
            BposChunk_KeyFrame(bone_count, reader) for _ in range(self.key_frame_count)
        ]


class BrotChunk_KeyFrame:

    time: float
    quternin_list: list[Quaternion]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.time = reader.read_float()

        self.quternin_list = [
            reader.read_quaternion() for _ in range(bone_count)
        ]


class BrotChunk:

    key_frame_count: int
    key_frame_list: list[BrotChunk_KeyFrame]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.key_frame_count = reader.read_uint32()
        self.key_frame_list = [
            BrotChunk_KeyFrame(bone_count, reader) for _ in range(self.key_frame_count)
        ]


class AnimationChunkReader(VisChunkFileReader):

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


class AnimationFileReader(AnimationChunkReader):

    def __init__(self, path: Path, context: bpy.types.Context) -> None:

        super().__init__(path)

        self.context = context
