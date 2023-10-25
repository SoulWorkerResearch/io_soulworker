

from io_soulworker.core.materials_xml.shader_param_string import ShaderParamString


class ShaderTag:

    def __init__(self, xml):

        self.paramstring = ShaderParamString(xml['Shader'])
