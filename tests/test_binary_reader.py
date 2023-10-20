
from logging import info
from unittest import TestCase

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_bin_header import VisBinHeader
from io_soulworker.core.vis_chunk_id import VisChunkId
from tests.defines import Defines


class TestBinaryReader(TestCase):

    def test(self):

        for file in Defines.TEST_FILES:
            info("(reader) Test file: %s", file)

            with BinaryReader(file) as reader:
                header = VisBinHeader(reader)

                self.assertEqual(header.cid, VisChunkId.VBIN)
                self.assertEqual(header.version, 65536)
