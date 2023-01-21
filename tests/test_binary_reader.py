
from pathlib import Path
from unittest import TestCase

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_bin_header import VisBinHeader
from io_soulworker.core.vis_chunk_id import VisChunkId


class TestBinaryReader(TestCase):

    def test(self):
        path = Path(
            "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Soulworker_KR\\datas\\CutScene\\ModelFile\\NPC\\NPC_0001_Mirium\\NPC_0001_Mirium.model")

        with BinaryReader(path) as reader:
            header = VisBinHeader(reader)

            self.assertEqual(header.cid, VisChunkId.VBIN)
            self.assertEqual(header.version, 65536)
