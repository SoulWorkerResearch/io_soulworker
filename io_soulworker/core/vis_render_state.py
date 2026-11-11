from ..core.binary_reader import BinaryReader
from ..core.binary_writer import BinaryWriter
from ..core.data_exchange import DataExchange_cl
from ..core.vis_render_state_flags import VisRenderStateFlag
from ..core.vis_transparency_type import VisTransparencyType


class VisRenderState(DataExchange_cl):

    transp_mode = VisTransparencyType.NONE
    unused = 0
    render_flags = VisRenderStateFlag.NONE

    def read(self, reader: BinaryReader) -> None:

        self.transp_mode = reader.read_transparency()
        self.unused = reader.read_uint8()
        self.render_flags = reader.read_render_state_flags()

    def write(self, writer: BinaryWriter) -> None:

        writer.write_transparency(self.transp_mode)
        writer.write_uint8(self.unused)
        writer.write_render_state_flags(self.render_flags)

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'VisRenderState':

        value = VisRenderState()
        value.read(reader)

        return value
