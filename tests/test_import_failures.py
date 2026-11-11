from __future__ import annotations

from pathlib import Path
from struct import pack, pack_into, unpack_from
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase

from io_soulworker.file_import.runner import in_blender


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_BOX = Path("tests/datas/Models/Primitive_Box.model")


def _chunk_ranges(data: bytes) -> dict[str, tuple[int, int]]:
    """Where the data of every top-level chunk starts and how long it is."""

    from io_soulworker.core.vis_chunk_id import VisChunkId

    ranges: dict[str, tuple[int, int]] = {}
    position = 8

    while unpack_from("<i", data, position)[0] >= 0:

        chunk, length = unpack_from("<iI", data, position + 4)
        ranges.setdefault(VisChunkId.get_name(chunk), (position + 12, length))
        position += 12 + length + 8

    return ranges


class TestReadErrors(TestCase):
    """What a user sees when a file is cut short, or is not a Vision file."""

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def test_short_read_says_the_file_ended_and_where(self):

        from io_soulworker.core.binary_reader import (
            BinaryReader,
            TruncatedFileError,
        )

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Short.bin"
            # One whole number, half of a second one, then a string that
            # claims more bytes than the file has.
            path.write_bytes(pack("<IH", 7, 1))
            long_string = Path(folder) / "String.bin"
            long_string.write_bytes(pack("<I", 100) + b"abc")

            with BinaryReader(path) as reader:

                self.assertEqual(reader.read_uint32(), 7)

                with self.assertRaises(TruncatedFileError) as number:
                    reader.read_uint32()

            with BinaryReader(long_string) as reader:

                with self.assertRaises(TruncatedFileError) as string:
                    reader.read_utf8_uint32_string()

        self.assertIsInstance(number.exception, EOFError)
        self.assertEqual(number.exception.offset, 4)
        self.assertIn("ends early", str(number.exception))
        self.assertIn("offset 4", str(number.exception))
        self.assertEqual(string.exception.offset, 4)

    def test_a_file_that_is_not_a_vision_file_is_rejected(self):

        from io_soulworker.core.vis_chunk_file import NotVisionFileError
        from io_soulworker.file_import.model.chunk_reader import (
            ModelChunkReader,
        )

        with TemporaryDirectory() as folder:

            for name, content in (
                ("Empty.model", b""),
                ("Short.model", b"VB"),
                ("Foreign.model", b"RIFF" + bytes(64)),
            ):

                path = Path(folder) / name
                path.write_bytes(content)

                with self.subTest(name), self.assertRaises(
                        NotVisionFileError) as raised:
                    ModelChunkReader(path).run()

                self.assertIn("VBIN", str(raised.exception))

    def test_a_chunk_that_runs_past_the_end_names_the_chunk(self):

        from io_soulworker.core.binary_reader import TruncatedFileError
        from io_soulworker.file_import.model.chunk_reader import (
            ModelChunkReader,
        )

        data = _BOX.read_bytes()
        start, length = _chunk_ranges(data)["MTRS"]

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Cut.model"
            path.write_bytes(data[:start + length // 2])

            with self.assertRaises(TruncatedFileError) as raised:
                ModelChunkReader(path).run()

        self.assertIn("MTRS", str(raised.exception))
        self.assertEqual(raised.exception.offset, start)

    def test_a_chunk_the_parser_rejects_names_the_chunk(self):

        from io_soulworker.core.vis_chunk_file import ChunkReadError
        from io_soulworker.core.vis_chunk_id import VisChunkId
        from io_soulworker.file_import.model.chunk_reader import (
            ModelChunkReader,
        )

        data = bytearray(_BOX.read_bytes())
        start, _ = _chunk_ranges(data)["MTRS"]

        # The surface count comes first, then the header of the first
        # surface. Break the id of that surface.
        pack_into("<i", data, start + 4 + 4, 0x12345678)

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Corrupt.model"
            path.write_bytes(data)

            with self.assertRaises(ChunkReadError) as raised:
                ModelChunkReader(path).run()

        self.assertEqual(raised.exception.chunk, VisChunkId.MTRS)
        self.assertIsInstance(raised.exception.__cause__, AssertionError)
        self.assertIn("unsupported or corrupt MTRS chunk",
                      str(raised.exception))

    def test_leaving_a_chunk_does_not_hide_the_error_of_a_cut_file(self):

        from io_soulworker.core.binary_reader import BinaryReader
        from io_soulworker.core.vis_chunk_id import VisChunkId
        from io_soulworker.core.vis_chunk_reader_scope import (
            VisChunkReaderScope,
        )

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Cut.bin"
            path.write_bytes(pack("<iiI", 0, VisChunkId.VMSH, 100))

            with BinaryReader(path) as reader:

                scope = VisChunkReaderScope(reader)
                scope.depth = 0
                scope.chunk = VisChunkId.VMSH
                scope.offset = 12
                scope.length = 100

                # The chunk claims 100 bytes the file does not have, so
                # finding its end fails as well. The caller must still get
                # the error that ended the chunk.
                original = ValueError("raised inside the chunk")

                self.assertFalse(
                    scope.__exit__(ValueError, original, None))
