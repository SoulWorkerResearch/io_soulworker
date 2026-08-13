from io import BytesIO
from logging import debug

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.binary_writer import BinaryWriter
from io_soulworker.core.data_exchange import DataExchange_cl
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_reader_scope import VisChunkReaderScope
from io_soulworker.core.vis_color import VisColor
from io_soulworker.core.vis_lighting_method import VisLightingMethod
from io_soulworker.core.vis_material_effect import VisMaterialEffect
from io_soulworker.core.vis_transparency_type import VisTransparencyType


class MtrsChunk(DataExchange_cl):

    LOCAL_VERSION = 2

    _envelope_enter_depth = 0
    _envelope_footer_stack_adj = 0

    version = LOCAL_VERSION
    name = ""
    flags = 0
    lighting_method = VisLightingMethod.FULLBRIGHT
    ui_sorting_key = 0
    spec_mul = 0.0
    spec_exp = 0.0
    transparency_type = VisTransparencyType.NONE
    ui_deferred_id = 0
    depth_bias = 0.0
    depth_bias_clamp = 0.0
    slope_scaled_depth_bias = 0.0
    custom_alpha_threshold = 0.0
    diffuse_map = ""
    specular_map = ""
    normal_map = ""
    aux_texture_paths: list[str]
    user_data = ""
    user_flags = 0
    ambient_color = VisColor()
    brightness = 0
    light_color = VisColor()
    parallax_scale = 0.0
    parallax_bias = 0.0
    config_effects: list[VisMaterialEffect]
    override_library = ""
    override_material = ""
    ui_mobile_shader_flags = 0

    def __init__(self) -> None:

        self.aux_texture_paths = []
        self.config_effects = []

    def read(self, reader: BinaryReader) -> None:

        with VisChunkReaderScope(reader) as scope:

            assert scope.chunk == VisChunkId.MTRL

            self._envelope_enter_depth = scope.depth

            self.version = reader.read_uint16()
            debug('version: %d', self.version)

            self.name = reader.read_utf8_uint32_string()
            debug("mat_name: %s", self.name)

            self.flags = reader.read_surface_flags()
            debug("flags: %s", repr(self.flags))

            if self.version >= 9:
                self.lighting_method = reader.read_lighting_method()

            self.ui_sorting_key = reader.read_uint32()

            assert self.ui_sorting_key < 16

            self.spec_mul = reader.read_float()
            self.spec_exp = reader.read_float()

            self.transparency_type = VisTransparencyType(reader.read_int8())

            self.ui_deferred_id = reader.read_uint8()

            if self.version >= 3:
                self.depth_bias = reader.read_float()

            if self.version >= 4:
                self.depth_bias_clamp = reader.read_float()
                self.slope_scaled_depth_bias = reader.read_float()

            if self.version >= 7:
                self.custom_alpha_threshold = reader.read_float()

            self.diffuse_map = reader.read_utf8_uint32_string()
            debug("diffuse path: %s", self.diffuse_map)

            self.specular_map = reader.read_utf8_uint32_string()
            debug("specular path: %s", self.specular_map)

            self.normal_map = reader.read_utf8_uint32_string()
            debug("normal path: %s", self.normal_map)

            if self.version >= 2:
                aux_count = reader.read_uint32()

                self.aux_texture_paths = MtrsChunk.__read_aux_names(
                    aux_count,
                    reader
                )

                for filename in self.aux_texture_paths:
                    debug("aux filename: %s", filename)

            self.user_data = reader.read_utf8_uint32_string()
            self.user_flags = reader.read_uint32()

            self.ambient_color = reader.read_color()

            self.brightness = reader.read_uint32()
            self.light_color = reader.read_color()

            self.parallax_scale = reader.read_float()
            self.parallax_bias = reader.read_float()

            self.config_effects = self.__read_mesh_config_effects(reader)

            if self.version >= 5:
                self.override_library = reader.read_utf8_uint32_string()
                self.override_material = reader.read_utf8_uint32_string()

            if 6 <= self.version < 8:
                self.ui_mobile_shader_flags = reader.read_int32()

    def write(self, writer: BinaryWriter) -> None:

        payload = BytesIO()
        payload_writer = BinaryWriter(payload)

        self.__write_payload(payload_writer)
        payload_writer.flush()
        raw = payload.getvalue()

        writer.write_int32(self._envelope_enter_depth)
        writer.write_cid(VisChunkId.MTRL)
        writer.write_uint32(len(raw))
        writer.write(raw)
        writer.write_int32(1)
        writer.write_cid(VisChunkId.MTRL)

    def __write_payload(self, writer: BinaryWriter) -> None:

        writer.write_uint16(self.version)
        writer.write_utf8_uint32_string(self.name)
        writer.write_uint32(int(self.flags))

        if self.version >= 9:
            writer.write_uint8(int(self.lighting_method))

        writer.write_uint32(self.ui_sorting_key)
        writer.write_float(self.spec_mul)
        writer.write_float(self.spec_exp)
        writer.write_uint8(int(self.transparency_type))
        writer.write_uint8(self.ui_deferred_id)

        if self.version >= 3:
            writer.write_float(self.depth_bias)

        if self.version >= 4:
            writer.write_float(self.depth_bias_clamp)
            writer.write_float(self.slope_scaled_depth_bias)

        if self.version >= 7:
            writer.write_float(self.custom_alpha_threshold)

        writer.write_utf8_uint32_string(self.diffuse_map)
        writer.write_utf8_uint32_string(self.specular_map)
        writer.write_utf8_uint32_string(self.normal_map)

        if self.version >= 2:
            writer.write_uint32(len(self.aux_texture_paths))
            for path in self.aux_texture_paths:
                writer.write_utf8_uint32_string(path)

        writer.write_utf8_uint32_string(self.user_data)
        writer.write_uint32(self.user_flags)
        writer.write_color(self.ambient_color)
        writer.write_uint32(self.brightness)
        writer.write_color(self.light_color)
        writer.write_float(self.parallax_scale)
        writer.write_float(self.parallax_bias)

        writer.write_uint32(len(self.config_effects))
        assert len(self.config_effects) <= 1

        for effect in self.config_effects:

            effect.version = self.version
            effect.write(writer)

        if self.version >= 5:
            writer.write_utf8_uint32_string(self.override_library)
            writer.write_utf8_uint32_string(self.override_material)

        if 6 <= self.version < 8:
            writer.write_uint32(self.ui_mobile_shader_flags)

    @staticmethod
    def __read_aux_names(count: int, reader: BinaryReader) -> list[str]:
        return [reader.read_utf8_uint32_string() for _ in range(count)]

    def __read_mesh_config_effects(self, reader: BinaryReader) -> list[VisMaterialEffect]:
        count = reader.read_uint32()
        assert count <= 1

        return [VisMaterialEffect.from_reader(reader, self.version) for _ in range(count)]

    @staticmethod
    def from_reader(reader: BinaryReader) -> 'MtrsChunk':

        value = MtrsChunk()
        value.read(reader)

        return value
