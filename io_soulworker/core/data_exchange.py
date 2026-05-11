from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter


class DataExchange_cl:

    def read(self, _: BinaryReader) -> None:
        raise NotImplementedError()

    def write(self, _: BinaryWriter) -> None:
        raise NotImplementedError()
