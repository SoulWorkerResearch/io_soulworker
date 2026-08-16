from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl


class VisShadowRelevanceChunk_cl(DataExchange_cl):
    """Packed bitfield shared by VSMR (per vertex) and TSMR (per triangle).

    Vision's VBaseMeshLoader reads ``ceil(count / 8)`` raw bytes and passes them
    to ``VDynamicMesh::SetShadowVertexRelevance`` / ``SetShadowTriangleRelevance``.
    Bit *i* lives in ``bits[i >> 3]`` as ``1 << (i & 7)`` (LSB-first within a byte).
    """

    bits: bytes = b""

    @staticmethod
    def packed_byte_count(element_count: int) -> int:

        return (element_count + 7) // 8

    def is_relevant(self, index: int) -> bool:

        return bool(self.bits[index >> 3] & (1 << (index & 7)))

    def read(self, reader: BinaryReader) -> None:

        raise NotImplementedError(
            "shadow relevance chunks require from_reader(reader, length)"
        )

    def write(self, writer: BinaryWriter) -> None:

        writer.write(self.bits)

    @classmethod
    def from_reader(
        cls,
        reader: BinaryReader,
        length: int,
    ) -> "VisShadowRelevanceChunk_cl":

        value = cls()
        value.bits = reader.read(length)
        return value


class VsmrChunk(VisShadowRelevanceChunk_cl):
    """VSMR — per-vertex shadow-mesh relevance."""


class TsmrChunk(VisShadowRelevanceChunk_cl):
    """TSMR — per-triangle shadow-mesh relevance."""
