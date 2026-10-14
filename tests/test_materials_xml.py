from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase
from xml.etree.ElementTree import parse

from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.file_export.materials_xml import (
    MaterialSidecar,
    materials_xml_path,
    write_materials_xml,
)
from io_soulworker.file_import.runner import in_blender


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)


class TestMaterialsXml(TestCase):

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def test_sidecar_path_uses_full_filename(self):

        self.assertEqual(
            materials_xml_path(Path("World/Meshes/Foo.vmesh")),
            Path("World/Meshes/Foo.vmesh_data/materials.xml"),
        )
        self.assertEqual(
            materials_xml_path(Path("Character/Bar.model")),
            Path("Character/Bar.model_data/materials.xml"),
        )

    def test_write_materials_xml_includes_shader_paramstring(self):

        sidecar = MaterialSidecar(
            name="MT_HAIR",
            diffuse=r"..\..\..\Textures\white.dds",
            transparency=VisTransparencyType.NONE,
            spec_mul=0.0,
            spec_exp=2.0,
            shader_library_stem="SWCellShading",
            shader_effect="HairTwotoneToonEffect",
            paramstring="FresnelExponent=0.25;glowColor=1,1,1;",
        )

        with TemporaryDirectory() as temp:

            xml_path = Path(temp) / "Hair.model_data" / "materials.xml"
            write_materials_xml(
                xml_path,
                [sidecar],
                resources_root=Path(temp) / "_datas",
            )

            root = parse(xml_path).getroot()
            material = root.find("Materials/Material")
            shader = material.find("Shader")

            self.assertEqual(material.attrib["name"], "MT_HAIR")
            self.assertEqual(material.attrib["transparency"], "opaque")
            self.assertEqual(material.attrib["specmul"], "0")
            self.assertEqual(shader.attrib["effect"], "HairTwotoneToonEffect")
            self.assertEqual(
                shader.attrib["paramstring"],
                "FresnelExponent=0.25;glowColor=1,1,1;",
            )
            self.assertTrue(
                shader.attrib["library"].replace("/", "\\").endswith(
                    r"Shaders\SWCellShading.ShaderLib"
                )
            )

    def test_write_materials_xml_omits_shader_without_effect(self):

        sidecar = MaterialSidecar(name="Default")

        with TemporaryDirectory() as temp:

            xml_path = Path(temp) / "Sphere.model_data" / "materials.xml"
            write_materials_xml(xml_path, [sidecar])

            root = parse(xml_path).getroot()
            material = root.find("Materials/Material")

            self.assertIsNone(material.find("Shader"))
            self.assertEqual(material.attrib["name"], "Default")
            self.assertTrue(xml_path.read_bytes().endswith(b"\n"))

    def test_mtrs_chunk_copies_shader_fields(self):

        sidecar = MaterialSidecar(
            name="MT_HAIR",
            shader_library_stem="SWCellShading",
            shader_effect="HairTwotoneToonEffect",
            paramstring="FresnelExponent=0.25;",
        )
        chunk = sidecar.to_mtrs_chunk()

        self.assertEqual(chunk.name, "MT_HAIR")
        self.assertEqual(len(chunk.config_effects), 1)
        self.assertEqual(
            chunk.config_effects[0].library,
            r"Shaders\SWCellShading.ShaderLib",
        )
        self.assertEqual(chunk.config_effects[0].name, "HairTwotoneToonEffect")
        self.assertEqual(
            chunk.config_effects[0].param, "FresnelExponent=0.25;")
