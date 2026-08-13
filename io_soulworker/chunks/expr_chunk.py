from mathutils import Matrix

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class ExprChunk(DataExchange_cl):
    """Mesh export transform (3x4 matrix) from Vision VBaseMesh loader."""

    LOCAL_VERSION = 1
    version = 0
    matrix = Matrix.Identity(4)
    flag = 0

    def read(self, reader: BinaryReader) -> None:

        self.version = reader.read_uint32()
        assert self.version == self.LOCAL_VERSION

        # Row-major 3x4 affine matrix (rotation/scale + translation).
        rows = [
            [reader.read_float() for _ in range(4)]
            for _ in range(3)
        ]

        rows.append([0.0, 0.0, 0.0, 1.0])

        self.matrix = Matrix(rows)

        self.flag = reader.read_uint8()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(self.version)

        for row_index in range(3):
            row = self.matrix[row_index]
            writer.write_float(row[0])
            writer.write_float(row[1])
            writer.write_float(row[2])
            writer.write_float(row[3])

        writer.write_uint8(self.flag)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "ExprChunk":

        value = ExprChunk()
        value.read(reader)

        return value
