from mathutils import Vector

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class ViewChunk(DataExchange_cl):
    """Editor / runtime camera (`VIEW`) from `.vscene`.

    Layout is a fixed 18-float block observed in KR scene files:
    near, far, position(3), forward(3), up(3), side(3), w, fov, reserved(2).
    """

    FLOAT_COUNT = 18

    values: list[float]

    def __init__(self) -> None:

        self.values = [0.0] * self.FLOAT_COUNT
        self.values[14] = 1.0
        self.values[15] = 60.0

    @property
    def near(self) -> float:
        return self.values[0]

    @near.setter
    def near(self, value: float) -> None:
        self.values[0] = value

    @property
    def far(self) -> float:
        return self.values[1]

    @far.setter
    def far(self, value: float) -> None:
        self.values[1] = value

    @property
    def position(self) -> Vector:
        return Vector(self.values[2:5])

    @position.setter
    def position(self, value: Vector) -> None:
        self.values[2:5] = [value.x, value.y, value.z]

    @property
    def forward(self) -> Vector:
        return Vector(self.values[5:8])

    @property
    def up(self) -> Vector:
        return Vector(self.values[8:11])

    @property
    def fov(self) -> float:
        return self.values[15]

    @fov.setter
    def fov(self, value: float) -> None:
        self.values[15] = value

    def read(self, reader: BinaryReader) -> None:

        self.values = [reader.read_float() for _ in range(self.FLOAT_COUNT)]

    def write(self, writer: BinaryWriter) -> None:

        for value in self.values:
            writer.write_float(value)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "ViewChunk":

        value = ViewChunk()
        value.read(reader)

        return value
