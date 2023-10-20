
from logging import info
from unittest import TestCase

from io_soulworker.out.model_file_reader import ModelFileReader
from tests.defines import Defines


class ChunkReader(ModelFileReader):
    pass


class TestModelImporter(TestCase):

    def test(self):

        for file in Defines.TEST_FILES:
            info("Test file: %s", file)

            reader = ChunkReader(file)
            reader.run()
