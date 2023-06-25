
from pathlib import Path
from unittest import TestCase

from io_soulworker.out.model_file_reader import ModelFileReader


class ChunkReader(ModelFileReader):
    pass


class TestModelImporter(TestCase):

    def test(self):
        path = Path(
            "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Soulworker_KR\\datas\\CutScene\\ModelFile\\NPC\\NPC_0001_Mirium\\NPC_0001_Mirium.model")

        reader = ChunkReader(path)
        reader.run()
