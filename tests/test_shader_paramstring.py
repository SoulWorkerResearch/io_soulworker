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
    sync_shader_node_groups,
)


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_LIBRARY = r"Shaders\Sample.ShaderLib"

_LIB = """
EFFECT Toon {
  DESCRIPTION = {};
  PARAMCOMMENT={"Strength","Strength","0.5",float,none,""};
  PARAMCOMMENT={"Tint","Tint","0.2,0.4,0.6",float3,color,""};
  PARAMCOMMENT={"Offset","Offset","1,2",float2,none,""};
  PARAMCOMMENT={"Rim","Rim","1,1,1,1",float4,color,""};
  PARAMCOMMENT={"Glow","Glow","0.75",float,none,""};
  PARAMCOMMENT={"MaskTexture","Mask","",texture,none,""};
  PARAMCOMMENT={"Proj","Proj","",float4x4,none,""};
}
EFFECT Other {
  DESCRIPTION = {};
  PARAMCOMMENT={"Strength","Strength","0.5",float,none,""};
}
"""

# What a game material looks like: entries the effect does not declare, the
# declared ones in an order of their own, numbers written in their own way,
# and one declared parameter (Glow) missing.
_SOURCE = (
    r"CullMode=back;Offset=3.0,4.250;Strength=1.50;PassType=pre_basepass;"
    r"Tint=0.9,0.8,0.7,1;Rim=-0.5,1,1,0.25;MaskTexture=Textures\mask.png;"
    r"Proj=1,0,0,0,0,1,0,0,0,0,1,0,5,6,7,1;"
)


class TestShaderParamString(TestCase):

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
        (self.root / "Shaders" / "Sample.ShaderLib").write_text(
            _LIB, encoding="cp949")
        sync_shader_node_groups(str(self.root))

        for name in ("mask", "other"):

            self._save_image(name)

    def tearDown(self) -> None:

        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _save_image(self, name: str):

        image = bpy.data.images.new(name, width=1, height=1)
        image.filepath_raw = str(self.root / "Textures" / f"{name}.png")
        image.file_format = "PNG"
        image.save()
        bpy.data.images.remove(image)

    def _import(self, paramstring: str = _SOURCE, effect: str = "Toon"):
        """A material the way the importer leaves it."""

        material = bpy.data.materials.new("Imported")
        material.use_nodes = True
        material["soulworker_shader_library"] = "Sample"
        material["soulworker_shader_effect"] = effect
        material["soulworker_shader_paramstring"] = ShaderParamString(
            paramstring).to_string()
        node = apply_shader_to_material(
            material,
            ShaderTag(Element(
                "Shader",
                library=_LIBRARY,
                effect=effect,
                paramstring=paramstring,
            )),
            self.root,
        )

        return material, node

    def _collect(self, material) -> str:

        return collect_shader_from_material(material, self.root)[2]

    def test_untouched_material_keeps_the_entries_and_order_of_its_source(self):

        material, _node = self._import()

        self.assertEqual(
            list(ShaderParamString(self._collect(material))),
            list(ShaderParamString(_SOURCE)),
        )

    def test_untouched_material_keeps_the_text_of_every_value(self):

        material, _node = self._import()

        self.assertEqual(self._collect(material), _SOURCE)

    def test_edited_socket_replaces_only_its_own_value(self):

        material, node = self._import()
        node.inputs["Strength"].default_value = 3.0

        self.assertEqual(
            self._collect(material),
            _SOURCE.replace("Strength=1.50", "Strength=3"),
        )

    def test_parameter_the_source_lacks_is_added_last_once_its_socket_changes(self):

        material, node = self._import()

        self.assertNotIn("Glow", ShaderParamString(self._collect(material)))

        node.inputs["Glow"].default_value = 2.0

        self.assertEqual(self._collect(material), _SOURCE + "Glow=2;")

        node.inputs["Glow"].default_value = 0.75

        self.assertNotIn("Glow", ShaderParamString(self._collect(material)))

    def test_texture_that_was_not_replaced_keeps_the_path_of_its_source(self):

        source = _SOURCE.replace(r"Textures\mask.png", r"textures\MASK.PNG")
        material, node = self._import(source)

        self.assertEqual(self._collect(material), source)

        node.inputs["MaskTexture"].links[0].from_node.image = bpy.data.images.load(
            str(self.root / "Textures" / "other.png"))

        self.assertEqual(
            self._collect(material),
            source.replace(r"textures\MASK.PNG", r"Textures\other.png"),
        )

    def test_node_group_of_another_effect_does_not_use_the_imported_string(self):

        material, _node = self._import(
            "CullMode=back;Strength=2.50;", effect="Other")
        material["soulworker_shader_effect"] = "Toon"

        self.assertEqual(self._collect(material), "Strength=2.5;")
