from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase
from xml.etree.ElementTree import Element

import bpy

from io_soulworker.core.materials_xml.shader_param_string import (
    ShaderParamString,
)
from io_soulworker.core.materials_xml.shader_tag import ShaderTag
from io_soulworker.file_import.runner import in_blender
from io_soulworker.file_import.shaders.node_groups import (
    apply_shader_to_material,
    collect_shader_from_material,
    find_effect_node_group,
    sync_shader_node_groups,
)


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_LIBRARY = r"Shaders\Sample.ShaderLib"

_LIB_V1 = """
EFFECT Toon {
  DESCRIPTION = {};
  PARAMCOMMENT={"Strength","Strength","0.5",float,none,""};
  PARAMCOMMENT={"Tint","Tint","0.2,0.4,0.6",float3,color,""};
  PARAMCOMMENT={"Offset","Offset","1,2",float2,none,""};
  PARAMCOMMENT={"MaskTexture","Mask","",texture,none,""};
}
"""

# Tint is gone, Extra is new and first, Offset changes its type.
_LIB_V2 = """
EFFECT Toon {
  DESCRIPTION = {};
  PARAMCOMMENT={"Extra","Extra","0.75",float,none,""};
  PARAMCOMMENT={"MaskTexture","Mask","",texture,none,""};
  PARAMCOMMENT={"Offset","Offset","0.1,0.2,0.3,0.4",float4,color,""};
  PARAMCOMMENT={"Strength","Strength","0.5",float,none,""};
}
"""


class TestShaderNodeGroups(TestCase):

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def setUp(self) -> None:

        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "Shaders").mkdir()
        (self.root / "Textures").mkdir()
        self._write_library(_LIB_V1)

        image = bpy.data.images.new("Mask", width=1, height=1)
        image.filepath_raw = str(self.root / "Textures" / "mask.png")
        image.file_format = "PNG"
        image.save()
        bpy.data.images.remove(image)

    def tearDown(self) -> None:

        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _write_library(self, text: str) -> None:

        (self.root / "Shaders" / "Sample.ShaderLib").write_text(
            text, encoding="cp949")

    def _sync(self) -> None:

        sync_shader_node_groups(str(self.root))

    def _place(self, paramstring: str):

        material = bpy.data.materials.new("Placed")
        material.use_nodes = True
        shader = ShaderTag(Element(
            "Shader",
            library=_LIBRARY,
            effect="Toon",
            paramstring=paramstring,
        ))
        node = apply_shader_to_material(material, shader, self.root)

        return material, node

    def _collect(self, material) -> ShaderParamString:

        library, effect, paramstring = collect_shader_from_material(
            material, self.root)

        self.assertEqual((library, effect), ("Sample", "Toon"))

        return ShaderParamString(paramstring)

    def test_sync_without_library_change_keeps_group_nodes(self):

        self._sync()
        material, node = self._place(
            r"Strength=2.5;Tint=0.9,0.8,0.7,1;Offset=3,4;"
            r"MaskTexture=Textures\mask.png;")
        node.inputs["Strength"].default_value = 7.0
        before = self._collect(material)
        identifiers = [socket.identifier for socket in node.inputs]

        self.assertEqual(before["Strength"], "7")
        self.assertTrue(node.inputs["MaskTexture"].is_linked)

        self._sync()

        self.assertEqual(self._collect(material), before)
        self.assertEqual(
            [socket.identifier for socket in node.inputs], identifiers)
        self.assertTrue(node.inputs["MaskTexture"].is_linked)

    def test_sync_after_library_change_keeps_remaining_parameters(self):

        self._sync()
        material, node = self._place(
            r"Strength=2.5;Tint=0.9,0.8,0.7,1;Offset=3,4;"
            r"MaskTexture=Textures\mask.png;")
        before = self._collect(material)

        self._write_library(_LIB_V2)
        self._sync()

        after = self._collect(material)

        self.assertEqual(
            list(after), ["Extra", "MaskTexture", "Offset", "Strength"])
        self.assertEqual(after["Strength"], before["Strength"])
        self.assertEqual(after["MaskTexture"], before["MaskTexture"])
        self.assertTrue(node.inputs["MaskTexture"].is_linked)
        # Added and retyped parameters take the ShaderLib default.
        self.assertEqual(after["Extra"], "0.75")
        self.assertEqual(after["Offset"], "0.1,0.2,0.3,0.4")
        group = find_effect_node_group(_LIBRARY, "Toon")
        self.assertEqual(
            [item.name for item in group.interface.items_tree],
            ["Extra", "MaskTexture", "Offset", "Strength"])
        self.assertEqual(
            [socket.name for socket in node.inputs],
            ["Extra", "MaskTexture", "Offset", "Strength"])

    def test_new_group_node_starts_with_shaderlib_defaults(self):

        self._sync()
        material, _node = self._place("")

        self.assertEqual(
            self._collect(material),
            ShaderParamString("Strength=0.5;Tint=0.2,0.4,0.6;Offset=1,2;"
                              "MaskTexture=;"))
