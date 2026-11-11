from logging import debug
from pathlib import Path

from io_soulworker.core.binary_reader import BinaryReader, TruncatedFileError
from io_soulworker.core.vis_bin_header import VisBinHeader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_reader_scope import VisChunkReaderScope


class NotVisionFileError(ValueError):
    """The file does not start with the ``VBIN`` header of a Vision file."""


class ChunkReadError(Exception):
    """A chunk of the file could not be read.

    ``chunk`` is the chunk that was being read and ``__cause__`` the error that
    stopped it. The message says what is wrong in words a user can act on.
    """

    def __init__(self, chunk: VisChunkId, cause: Exception) -> None:

        self.chunk = chunk

        super().__init__(ChunkReadError.describe(chunk, cause))

    @staticmethod
    def describe(chunk: VisChunkId, cause: Exception) -> str:

        name = VisChunkId.get_name(chunk)

        if isinstance(cause, TruncatedFileError):

            return f"{cause} (inside the {name} chunk)"

        # The chunk parsers check what they read with ``assert``; an enum
        # constructor refuses an unknown value with ``ValueError``; a count
        # or an index that is out of range ends in the other errors.
        if isinstance(cause, AssertionError):

            return f"unsupported or corrupt {name} chunk"

        if isinstance(
                cause, (ValueError, IndexError, KeyError, OverflowError)):

            return (
                f"unsupported or corrupt {name} chunk "
                f"({type(cause).__name__}: {cause})"
            )

        return (
            f"the {name} chunk could not be read "
            f"({type(cause).__name__}: {cause})"
        )


class VisChunkFileReader(object):

    current_chunk = VisChunkId.NONE
    """The chunk being read; ``NONE`` between chunks."""

    def __init__(self, path: Path) -> None:

        self.path = path

    def on_chunk_start(
            self,
            scope: VisChunkReaderScope,
            _: BinaryReader) -> None:

        raise NotImplementedError("chunk: %d" % scope.chunk)

    def run_sub(
            self,
            reader: BinaryReader,
            parent: VisChunkReaderScope) -> None:

        eof = parent.offset + parent.length

        debug("length: %d", parent.length)
        debug("current: %d", reader.tell())
        debug("eof: %d", eof)

        while reader.tell() < eof:

            with VisChunkReaderScope(reader) as scope:

                self.current_chunk = scope.chunk
                self.on_chunk_start(scope, reader)

            self.current_chunk = parent.chunk

    def run(self) -> None:

        with BinaryReader(self.path) as reader:

            self._read_header(reader)

            try:

                self._read_chunks(reader)

            except (ChunkReadError, NotVisionFileError):

                raise

            except Exception as exc:

                # An error between chunks (a cut chunk header) already says
                # what is wrong; inside a chunk, name the chunk.
                if self.current_chunk == VisChunkId.NONE:

                    raise

                raise ChunkReadError(self.current_chunk, exc) from exc

    def _read_header(self, reader: BinaryReader) -> None:

        try:

            header = VisBinHeader.from_reader(reader)

        except TruncatedFileError as exc:

            raise NotVisionFileError(
                "the file is too short to hold the VBIN header of a "
                "Vision file"
            ) from exc

        if header.cid != VisChunkId.VBIN:

            raise NotVisionFileError(
                "the file does not start with the VBIN header of a Vision "
                "file"
            )

        debug("version: %d", header.version)

    def _read_chunks(self, reader: BinaryReader) -> None:

        self.current_chunk = VisChunkId.NONE

        while True:

            with VisChunkReaderScope(reader) as scope:

                self.current_chunk = scope.chunk
                self.on_chunk_start(scope, reader)

                if scope.depth < 0:

                    break

            self.current_chunk = VisChunkId.NONE
