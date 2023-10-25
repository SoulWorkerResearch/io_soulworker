

from io_soulworker.core.binary_reader import BinaryReader


class VisMaterialEffect:

    def __init__(self, version: int, reader: BinaryReader) -> None:

        self.library = reader.read_utf8_uint32_string()
        self.name = reader.read_utf8_uint32_string()
        self.param = reader.read_utf8_uint32_string()

        if version >= 7:
            self.template_name = reader.read_utf8_uint32_string()
