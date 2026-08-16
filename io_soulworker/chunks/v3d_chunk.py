from struct import unpack

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class V3dChunk(DataExchange_cl):
    """3D scene settings (`_V3D`): light-grid path and shader provider."""

    version = 0
    unknown0 = 0
    unknown1 = -1
    has_lightgrid = 0
    unknown_flag = 0
    lightgrid_path = ""
    shader_provider = ""

    def read(self, reader: BinaryReader) -> None:

        self.version = reader.read_uint32()
        self.unknown0 = reader.read_uint32()
        self.unknown1 = reader.read_int32()
        self.has_lightgrid = reader.read_uint32()
        self.unknown_flag = reader.read_uint8()
        self.lightgrid_path = self._read_optional_string(reader)
        self.shader_provider = self._read_optional_string(reader)

    def write(self, writer: BinaryWriter) -> None:

        writer.write_uint32(self.version)
        writer.write_uint32(self.unknown0)
        writer.write_int32(self.unknown1)
        writer.write_uint32(self.has_lightgrid)
        writer.write_uint8(self.unknown_flag)
        self._write_optional_string(writer, self.lightgrid_path)
        self._write_optional_string(writer, self.shader_provider)

    @staticmethod
    def _read_optional_string(reader: BinaryReader) -> str:
        """Length-prefixed cp949 string; `0xFFFFFFFF` means empty."""

        length = reader.read_uint32()

        if length == 0xFFFFFFFF:
            return ""

        value, = unpack("<%ds" % length, reader.read(length))

        return value.decode("cp949")

    @staticmethod
    def _write_optional_string(writer: BinaryWriter, value: str) -> None:

        if value == "":
            writer.write_uint32(0xFFFFFFFF)
            return

        writer.write_utf8_uint32_string(value)

    @staticmethod
    def from_reader(reader: BinaryReader) -> "V3dChunk":

        value = V3dChunk()
        value.read(reader)

        return value
