from pathlib import Path
from unittest import TestCase
from io_soulworker.chunks.mtrs_chunk import MtrsChunk

from io_soulworker.core.binary_reader import BinaryReader


class TestVisSurface(TestCase):
    def test(self):
        with BinaryReader("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Soulworker_KR\\datas\\CutScene\\ModelFile\\NPC\\NPC_0001_Mirium\\NPC_0001_Mirium.model_chunks\\MTRS") as reader:
            count = reader.read_uint32()

            p = Path('C:\\Program Files (x86)\\Steam\\steamapps\\common\\Soulworker_KR\\datas\\CutScene\\ModelFile\\NPC\\NPC_0001_Mirium\\NPC_0001_Mirium.model')
            for _ in range(count):
                MtrsChunk(reader).load_material(p)
