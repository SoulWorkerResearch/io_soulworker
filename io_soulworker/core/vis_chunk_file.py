from logging import debug
from pathlib import Path

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_bin_header import VisBinHeader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_scope import VisChunkScope


class VisChunkFileReader(object):

    def __init__(self, path: Path) -> None:
        self.path = path

    def on_chunk_start(self, chunk: VisChunkId, _: BinaryReader) -> None:
        raise NotImplementedError("chunk: %d" % chunk)

    def run(self) -> None:
        with BinaryReader(self.path) as reader:
            header = VisBinHeader(reader)
            debug("[VisChunkFile] version: ", header.version)

            while True:
                with VisChunkScope(reader) as scope:
                    self.on_chunk_start(scope.cid, reader)

                    if scope.depth < 0:
                        break
