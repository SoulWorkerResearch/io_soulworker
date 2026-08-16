from pathlib import Path

from io_soulworker.chunks.eplg_chunk import EplgChunk
from io_soulworker.chunks.scne_chunk import ScneChunk
from io_soulworker.chunks.shps_chunk import ShpsChunk
from io_soulworker.chunks.st5g_chunk import St5gChunk
from io_soulworker.chunks.v3d_chunk import V3dChunk
from io_soulworker.chunks.view_chunk import ViewChunk
from io_soulworker.chunks.zone_chunk import ZoneChunk
from io_soulworker.file_import.scene.chunk_reader import SceneChunkReader


class SceneFileReader(SceneChunkReader):
    """Collects parsed `.vscene` chunks for inspection / import."""

    def __init__(self, path: Path) -> None:

        super().__init__(path)

        self.scene: ScneChunk | None = None
        self.plugins: EplgChunk | None = None
        self.v3d: V3dChunk | None = None
        self.view: ViewChunk | None = None
        self.zone: ZoneChunk | None = None
        self.shapes: ShpsChunk | None = None
        self.sky: St5gChunk | None = None

    def on_scene(self, chunk: ScneChunk) -> None:
        self.scene = chunk

    def on_plugins(self, chunk: EplgChunk) -> None:
        self.plugins = chunk

    def on_v3d(self, chunk: V3dChunk) -> None:
        self.v3d = chunk

    def on_view(self, chunk: ViewChunk) -> None:
        self.view = chunk

    def on_zone(self, chunk: ZoneChunk) -> None:
        self.zone = chunk

    def on_shapes(self, chunk: ShpsChunk) -> None:
        self.shapes = chunk

    def on_sky(self, chunk: St5gChunk) -> None:
        self.sky = chunk
