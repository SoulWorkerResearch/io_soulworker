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

    def test_stored_surface_fields_override_heuristics(self):
        from io_soulworker.core.vis_surface_flags import VisSurfaceFlags

        sidecar = MaterialSidecar(
            name="MT_BODY",
            diffuse=r"Textures\body.dds",
            transparency=VisTransparencyType.ALPHA,
            doublesided=True,
            alphathreshold=0.5,
            mtrs_fields={
                "transparency_type": int(VisTransparencyType.NONE),
                "custom_alpha_threshold": 0.25,
                "flags": 2,
                "ambient_color": [150, 150, 150, 255],
                "config_effects": [],
            },
            xml_attributes={
                "name": "IGNORED",
                "diffuse": "IGNORED.dds",
                "transparency": "opaque",
                "doublesided": "FALSE",
                "ambient": "150,150,150,255",
                "alphathreshold": "0.25",
                "pass": "AUTO",
                "mobileflags": "0",
            },
        )

        chunk = sidecar.to_mtrs_chunk()

        self.assertEqual(chunk.name, "MT_BODY")
        self.assertEqual(chunk.transparency_type, VisTransparencyType.NONE)
        self.assertEqual(chunk.custom_alpha_threshold, 0.25)
        self.assertEqual(chunk.flags, VisSurfaceFlags(2))
        self.assertEqual(
            (chunk.ambient_color.r, chunk.ambient_color.g,
             chunk.ambient_color.b, chunk.ambient_color.a),
            (150, 150, 150, 255),
        )
        self.assertEqual(chunk.config_effects, [])

        with TemporaryDirectory() as temp:

            xml_path = Path(temp) / "Body.model_data" / "materials.xml"
            write_materials_xml(xml_path, [sidecar])
            row = parse(xml_path).getroot().find("Materials/Material")

        self.assertEqual(row.attrib["name"], "MT_BODY")
        self.assertEqual(row.attrib["diffuse"], r"Textures\body.dds")
        self.assertEqual(row.attrib["transparency"], "opaque")
        self.assertEqual(row.attrib["doublesided"], "FALSE")
        self.assertEqual(row.attrib["ambient"], "150,150,150,255")
        self.assertEqual(row.attrib["pass"], "AUTO")
        self.assertEqual(row.attrib["mobileflags"], "0")

    def test_map_attributes_follow_sidecar_paths(self):

        with TemporaryDirectory() as temp:

            xml_path = Path(temp) / "Maps.model_data" / "materials.xml"
            write_materials_xml(xml_path, [
                MaterialSidecar(name="Plain"),
                MaterialSidecar(name="Spec", specular=r"Textures\spec.dds"),
                MaterialSidecar(
                    name="Stored",
                    xml_attributes={"specularmap": "stale\\old.dds",
                                    "normalmap": ""},
                ),
            ])
            rows = parse(xml_path).getroot().findall("Materials/Material")

        plain, spec, stored = rows
        self.assertNotIn("specularmap", plain.attrib)
        self.assertNotIn("normalmap", plain.attrib)
        self.assertEqual(spec.attrib["specularmap"], r"Textures\spec.dds")
        self.assertNotIn("normalmap", spec.attrib)
        self.assertEqual(stored.attrib["specularmap"], "")
        self.assertEqual(stored.attrib["normalmap"], "")

    def test_mtrs_chunk_round_trips_through_dict(self):
        from io_soulworker.chunks.mtrs_chunk import MtrsChunk
        from io_soulworker.core.vis_surface_flags import VisSurfaceFlags

        chunk = MaterialSidecar(name="X").to_mtrs_chunk()
        chunk.flags = VisSurfaceFlags(2)
        chunk.transparency_type = VisTransparencyType.ADDITIVE
        chunk.custom_alpha_threshold = 0.125
        chunk.aux_texture_paths = ["a.dds"]

        clone = MtrsChunk()
        clone.apply_dict(chunk.to_dict())

        self.assertEqual(clone.to_dict(), chunk.to_dict())
        self.assertEqual(clone.flags, VisSurfaceFlags(2))
        self.assertEqual(clone.transparency_type, VisTransparencyType.ADDITIVE)

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
