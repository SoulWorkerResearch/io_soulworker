from ..core.binary_reader import BinaryReader
from ..core.binary_writer import BinaryWriter


class DataExchange_cl:

    def read(self, _: BinaryReader) -> None:
        raise NotImplementedError()

    def write(self, _: BinaryWriter) -> None:
        raise NotImplementedError()
