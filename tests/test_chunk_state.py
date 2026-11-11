from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase


class TestChunkState(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import mathutils  # noqa: F401
        except ImportError as exc:
            raise SkipTest("requires mathutils") from exc

    @contextmanager
    def _reader(self, data: bytes):
        from io_soulworker.core.binary_reader import BinaryReader

        with TemporaryDirectory() as folder:
            path = Path(folder) / "chunk.bin"
            path.write_bytes(data)

            with BinaryReader(path) as reader:
                yield reader

    def test_bbbx_entities_keep_their_own_boxes(self):
        from io_soulworker.chunks.bbbx_chunk import BBBXChunk

        boxes = [
            (-1.0, -2.0, -3.0, 1.0, 2.0, 3.0),
            (-4.0, -5.0, -6.0, 4.0, 5.0, 6.0),
            (-7.0, -8.0, -9.0, 7.0, 8.0, 9.0),
        ]
        data = pack("<H", len(boxes)) + b"".join(
            pack("<6f", *box) for box in boxes)

        with self._reader(data) as reader:
            chunk = BBBXChunk.from_reader(reader)

        self.assertEqual(len(chunk.values), len(boxes))

        for entity, box in zip(chunk.values, boxes):
            self.assertEqual(tuple(entity.bounds.min), box[:3])
            self.assertEqual(tuple(entity.bounds.max), box[3:])

        self.assertIsNot(chunk.values[0].bounds, chunk.values[1].bounds)
