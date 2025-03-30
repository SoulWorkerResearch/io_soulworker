
from logging import info
from unittest import TestCase

from io_soulworker.file_import.model.file_reader import ModelLileReader
from tests.defines import Defines


class ChunkReader(ModelLileReader):
    pass


class TestModelImporter(TestCase):

    def test(self):

        for file in Defines.TEST_FILES:
            info("(importer) Test file: %s", file)

            reader = ChunkReader(file)
            reader.run()
