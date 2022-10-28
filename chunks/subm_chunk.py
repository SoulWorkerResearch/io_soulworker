
from io_soulworker.core.binary_reader import BinaryReader


class VisVerticesMaterial:

    def __init__(self, reader: BinaryReader) -> None:
        self.indices_start = reader.read_int32()
        self.indices_count = reader.read_int32()
        self.u6 = reader.read_int32()
        self.u7 = reader.read_int32()
        self.u8 = reader.read_int32()
        self.u9 = reader.read_int32()
        self.u10 = reader.read_int32()
        self.u11 = reader.read_int32()

        self.u12 = reader.read_float()
        self.u13 = reader.read_float()
        self.u14 = reader.read_float()
        self.u15 = reader.read_float()
        self.u16 = reader.read_float()
        self.u17 = reader.read_float()

        self.id = reader.read_int32()
        self.u18 = reader.read_int32()


class SubmChunk:

    def __init__(self, reader: BinaryReader) -> None:
        self.u1 = reader.read_int32()
        if self.u1 < 0:
            self.u2 = reader.read_int32()
            if self.u2 >= 2:
                self.geometry_count = reader.read_int32()
                assert self.geometry_count == 0

            count = reader.read_uint32()
            self.materials = self.__materials(count, reader)

    def __materials(self, count: int, reader: BinaryReader):
        return [VisVerticesMaterial(reader) for _ in range(count)]
