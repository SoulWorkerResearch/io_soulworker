from logging import debug
from logging import warn
from pathlib import Path
from xml.etree.ElementTree import parse

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.core.vis_chunk_stack_scope import VisChunkStackScope
from io_soulworker.core.vis_material_effect import VisMaterialEffect


class MtrsChunk:

    def __init__(self, reader: BinaryReader) -> None:
        with VisChunkStackScope(reader) as scope:
            assert scope.cid == VisChunkId.MTRL

            version = reader.read_uint16()
            debug('version: %d', version)

            self.name = reader.read_utf8_uint32_string()
            debug("mat_name: %s", self.name)

            self.flags = reader.read_uint32()
            debug("flags: %s", repr(self.flags))

            self.ui_sorting_key = reader.read_uint32()
            """ internal sorting key; has to be in the range 0..15 """

            self.spec_mul = reader.read_float()
            """ Specular multiplier for material for the Vision engine """

            self.spec_exp = reader.read_float()
            """ Specular exponent for materials for the Vision engine """

            self.transparency_type = reader.read_transparency()

            self.ui_deferred_id = reader.read_uint8()
            """ material ID that is written to G-Buffer in deferred rendering """

            if version >= 3:
                self.depth_bias = reader.read_float()
                """ z-offset value that is passed to the shader """

            if version >= 4:
                self.depth_bias_clamp = reader.read_float()
                """ clamped z-offset value that is passed to the shader """

                self.slope_scaled_depth_bias = reader.read_float()
                """ slope dependent z-offset value that is passed to the shader """

            self.diffuse_map = reader.read_utf8_uint32_string()
            debug("diffuse path: %s", self.diffuse_map)

            self.specular_map = reader.read_utf8_uint32_string()
            debug("specular path: %s", self.specular_map)

            self.normal_map = reader.read_utf8_uint32_string()
            debug("normal path: %s", self.normal_map)

            if version >= 2:
                count = reader.read_uint32()
                aux_filenames = MtrsChunk.__names(count, reader)

                for filename in aux_filenames:
                    debug("aux filename: %s", filename)

            self.user_data = reader.read_utf8_uint32_string()
            """ user data string set in editing tools (e.g. vEdit, Maya) """

            self.user_flags = reader.read_uint32()
            """ customizable user flags """

            self.ambient_color = reader.read_color()
            """ the ambient color of this surface """

            reader.read_uint32()  # some unused (maybe colors)
            reader.read_uint32()  # some unused (maybe colors)

            self.parallax_scale = reader.read_float()
            """ parallax scale """

            self.parallax_bias = reader.read_float()
            """ parallax bias """

            self.config_effects = MtrsChunk.__mesh_config_effects(reader)

            if version >= 5:
                self.override_library = reader.read_utf8_uint32_string()
                self.override_material = reader.read_utf8_uint32_string()

            if version >= 6:
                self.ui_mobile_shader_flags = reader.read_uint32()

    def __names(count: int, reader: BinaryReader):
        return [reader.read_utf8_uint32_string(reader) for _ in range(count)]

    def __mesh_config_effects(reader: BinaryReader) -> list[VisMaterialEffect]:
        count = reader.read_uint32()
        return [VisMaterialEffect(reader) for _ in range(count)]
