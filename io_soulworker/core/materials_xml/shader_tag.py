

from xml.etree.ElementTree import Element

from io_soulworker.core.materials_xml.shader_param_string import ShaderParamString


class ShaderTag:

    def __init__(self, node: Element):

        self.paramstring = ShaderParamString(node.attrib['paramstring'])
