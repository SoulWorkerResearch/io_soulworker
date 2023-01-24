
from io_soulworker.core.binary_reader import BinaryReader


class VisVerticesMaterial:

    def __init__(self, materials: int, version: int, reader: BinaryReader) -> None:
        self.indices_start = reader.read_int32()
        self.indices_count = reader.read_int32()
        self.u6 = reader.read_int32()
        self.u7 = reader.read_int32()
        self.first_vertex = reader.read_int32()
        self.num_vertices = reader.read_int32()
        self.u10 = reader.read_int32()
        self.u11 = reader.read_int32()

        self.bounding_box = reader.read_float_vector3()
        self.bounding_box_max = reader.read_float_vector3()

        self.id = reader.read_int32()

        if version < 2:
            if version < 1:
                _ = reader.read_int32()
                _ = reader.read_int16()
                _ = reader.read_int16()
                _ = reader.read_uint8()
                _ = reader.read_uint8()
                _ = reader.read_float()
                _ = reader.read_float()
        else:
            geometry_index = reader.read_int32()
            assert materials >= geometry_index

        self.u18 = reader.read_int32()


class SubmChunk:

    def __init__(self, reader: BinaryReader) -> None:
        self.iSubMeshCount = reader.read_int32()
        if self.iSubMeshCount < 0:
            self.version = reader.read_int32()
            if self.version >= 2:
                self.geometry_count = reader.read_int32()

                # geometry info implemented
                assert self.geometry_count == 0

            count = reader.read_uint32()
            self.materials = self.__materials(count, reader)

    def __materials(self, count: int, reader: BinaryReader):
        return [VisVerticesMaterial(count, self.version, reader) for _ in range(count)]
