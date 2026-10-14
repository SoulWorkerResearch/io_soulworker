from __future__ import annotations

from unittest import TestCase

from io_soulworker.core.materials_xml.shader_param_string import (
    ShaderParamString,
    format_param_float,
    format_paramstring,
    paramstring_from_params,
)
from io_soulworker.core.shader_lib import (
    parse_shader_lib_file,
    parse_shader_lib_text,
)
from tests.defines import Defines


_SAMPLE_LIB = """
EFFECT SomeShaderName {
  DESCRIPTION = {};
  PARAMCOMMENT={"FresnelExponent","FresnelExponent","0.25",float,none,""};
  PARAMCOMMENT={"glowColor","GlowColor","0,1,0.3333333,1",float3,color,""};
}
"""


class TestShaderLib(TestCase):

    def test_parse_paramcomment_and_paramstring(self):

        library = parse_shader_lib_text(_SAMPLE_LIB, stem="Sample")
        effect = library.effects["SomeShaderName"]

        self.assertEqual(len(effect.params), 2)
        self.assertEqual(effect.params[0].name, "FresnelExponent")
        self.assertEqual(effect.params[0].default, "0.25")
        self.assertEqual(effect.params[0].value_type, "float")
        self.assertEqual(effect.params[1].name, "glowColor")

        encoded = paramstring_from_params(
            effect.params,
            {"FresnelExponent": "0.5"},
        )

        self.assertEqual(
            encoded,
            "FresnelExponent=0.5;glowColor=0,1,0.3333333,1;",
        )

        parsed = ShaderParamString(encoded)

        self.assertEqual(parsed["FresnelExponent"], "0.5")
        self.assertEqual(parsed["glowColor"], "0,1,0.3333333,1")
        self.assertEqual(parsed.to_string(), encoded)

    def test_format_param_float(self):

        self.assertEqual(format_param_float(1.0), "1")
        self.assertEqual(format_param_float(0.25), "0.25")
        self.assertEqual(format_param_float(0.2509804), "0.2509804")

    def test_format_paramstring_skips_empty_names(self):

        self.assertEqual(format_paramstring([]), "")
        self.assertEqual(
            format_paramstring([("A", "1"), ("", "x")]),
            "A=1;",
        )

    def test_scan_real_shaderlib_when_present(self):

        path = Defines.UNPACKED_RESOURCES / "Shaders" / "SW_Enviroment.ShaderLib"

        if not path.is_file():

            self.skipTest(f"ShaderLib not found: {path}")

        library = parse_shader_lib_file(path)
        found = None

        for effect in library.effects.values():

            for param in effect.params:

                if param.name == "FresnelExponent":

                    found = param
                    break

            if found is not None:

                break

        self.assertIsNotNone(found)
        self.assertEqual(found.default, "0.25")
        self.assertEqual(found.value_type, "float")
