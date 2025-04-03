from logging import debug
from pathlib import Path

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_bin_header import VisBinHeader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_reader_scope import VisChunkReaderScope


class VisChunkFileReader(object):

    def __init__(self, path: Path) -> None:

        self.path = path

    def on_chunk_start(self, scope: VisChunkReaderScope, reader: BinaryReader) -> None:

        raise NotImplementedError("chunk: %d" % scope.chunk)

    def run_sub(self, reader: BinaryReader, parent: VisChunkReaderScope) -> None:

        eof = parent.offset + parent.length

        debug("length: %d", parent.length)
        debug("current: %d", reader.tell())
        debug("eof: %d", eof)

        while reader.tell() < eof:

            with VisChunkReaderScope(reader) as scope:

                self.on_chunk_start(scope, reader)

    def run(self) -> None:

        with BinaryReader(self.path) as reader:

            header = VisBinHeader(reader)
            debug("version: %d", header.version)

            while True:

                with VisChunkReaderScope(reader) as scope:

                    self.on_chunk_start(scope, reader)

                    if scope.depth < 0:

                        break
