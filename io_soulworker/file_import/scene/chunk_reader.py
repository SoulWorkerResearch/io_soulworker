from logging import debug, info

from io_soulworker.chunks.eplg_chunk import EplgChunk
from io_soulworker.chunks.scne_chunk import ScneChunk
from io_soulworker.chunks.shps_chunk import ShpsChunk
from io_soulworker.chunks.st5g_chunk import St5gChunk
from io_soulworker.chunks.v3d_chunk import V3dChunk
from io_soulworker.chunks.view_chunk import ViewChunk
from io_soulworker.chunks.zone_chunk import ZoneChunk
from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_file import VisChunkFileReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_reader_scope import VisChunkReaderScope


class SceneChunkReader(VisChunkFileReader):
    """Chunk dispatcher for Vision `.vscene` files."""

    def __init__(self, path) -> None:

        super().__init__(path)
        self._scene_version = 14

    def on_scene(self, chunk: ScneChunk) -> None:
        debug("Not impl callback")

    def on_plugins(self, chunk: EplgChunk) -> None:
        debug("Not impl callback")

    def on_v3d(self, chunk: V3dChunk) -> None:
        debug("Not impl callback")

    def on_view(self, chunk: ViewChunk) -> None:
        debug("Not impl callback")

    def on_zone(self, chunk: ZoneChunk) -> None:
        debug("Not impl callback")

    def on_shapes(self, chunk: ShpsChunk) -> None:
        debug("Not impl callback")

    def on_sky(self, chunk: St5gChunk) -> None:
        debug("Not impl callback")

    def on_chunk_start(self, scope: VisChunkReaderScope, reader: BinaryReader) -> None:

        info("read chunk: %s", VisChunkId.get_name(scope.chunk))

        match scope.chunk:
            case VisChunkId.SCNE:
                scene = ScneChunk.from_reader(reader)
                self._scene_version = scene.version
                self.on_scene(scene)

            case VisChunkId.EPLG:
                self.on_plugins(EplgChunk.from_reader(reader))

            case VisChunkId._V3D:
                self.on_v3d(V3dChunk.from_reader(reader))

            case VisChunkId.VIEW:
                self.on_view(ViewChunk.from_reader(reader))

            case VisChunkId.ZONE:
                self.on_zone(ZoneChunk.from_reader(reader))

            case VisChunkId.SHPS:
                self.on_shapes(ShpsChunk.from_reader(
                    reader,
                    scope.length,
                    scene_version=self._scene_version,
                ))

            case VisChunkId.ST5G:
                self.on_sky(St5gChunk.from_reader(reader))

            case _:
                debug("Not impl callback: %s", VisChunkId.get_name(scope.chunk))
