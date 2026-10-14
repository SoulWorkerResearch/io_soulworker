from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from xml.etree.ElementTree import parse

from io_soulworker.file_export.materials_xml import MaterialSidecar
from io_soulworker.file_export.resources_xml import (
    resolve_export_path,
    resources_xml_path,
    write_export_sidecars,
)


class TestResourcesXml(TestCase):

    def test_sidecar_path_uses_full_filename(self):

        self.assertEqual(
            resources_xml_path(Path("World/Meshes/Foo.vmesh")),
            Path("World/Meshes/Foo.vmesh_data/resources.xml"),
        )
        self.assertEqual(
            resources_xml_path(Path("Character/Bar.model")),
            Path("Character/Bar.model_data/resources.xml"),
        )

    def test_resolve_export_path_writes_inside_directory(self):

        with TemporaryDirectory() as temp:

            dest = Path(temp) / "export-test"
            dest.mkdir()
            path = resolve_export_path(dest, "NPC_0001_Mirium", ".model")

            self.assertEqual(path, dest / "NPC_0001_Mirium.model")

            missing = Path(temp) / "missing-folder"
            created = resolve_export_path(missing, "Cube", ".vmesh")

            self.assertTrue(missing.is_dir())
            self.assertEqual(created, missing / "Cube.vmesh")

    def test_resolve_export_path_keeps_explicit_filename(self):

        with TemporaryDirectory() as temp:

            dest = Path(temp) / "Hero.model"
            path = resolve_export_path(dest, "Ignored", ".model")

            self.assertEqual(path, dest)

    def test_write_export_sidecars_lists_textures_and_mesh(self):

        sidecar = MaterialSidecar(
            name="MT_CLOTH",
            diffuse=r"Character\NPC\NPC_0001_Mirium\Textures\NPC_0001_Mirium.dds",
            shader_library_stem="SWCellShading",
            shader_effect="ClothesToonEffect",
            paramstring=(
                r"ToonTexture=Textures\ToonTexture.dds;"
                r"DarknessClothesMaskTexture=Character\NPC\NPC_0001_Mirium"
                r"\Textures\NPC_0001_Mirium_Mask_01.dds;"
            ),
        )

        with TemporaryDirectory() as temp:

            mesh_path = Path(temp) / "NPC_0001_Mirium.model"
            mesh_path.write_bytes(b"mesh")
            data_dir = write_export_sidecars(mesh_path, [sidecar])

            materials_path = data_dir / "materials.xml"
            resources_path = data_dir / "resources.xml"

            self.assertTrue(materials_path.is_file())
            self.assertTrue(resources_path.is_file())
            self.assertTrue(resources_path.read_bytes().endswith(b"\n"))

            resources = parse(resources_path).getroot().find("Resources")
            self.assertIsNotNone(resources)
            self.assertEqual(resources.attrib["PathType"], "Project")

            rows = list(resources)
            managers = [row.attrib["Manager"] for row in rows]
            filenames = [row.attrib["Filename"] for row in rows]

            self.assertEqual(resources.attrib["Count"], str(len(rows)))
            self.assertEqual(
                managers,
                [
                    "Textures",
                    "Textures",
                    "Textures",
                    "EffectLibs",
                    "FILE",
                    "Static/Dynamic Meshes",
                ],
            )
            self.assertEqual(
                filenames[0],
                r"Character\NPC\NPC_0001_Mirium\Textures\NPC_0001_Mirium.dds",
            )
            self.assertEqual(rows[0].attrib["CustomInt"], "1,64")
            self.assertEqual(filenames[1], r"Textures\ToonTexture.dds")
            self.assertEqual(rows[1].attrib["CustomInt"], "1,0")
            self.assertEqual(
                filenames[3],
                r"Shaders\SWCellShading.ShaderLib",
            )
            self.assertEqual(
                filenames[4],
                r"NPC_0001_Mirium.model_data\materials.xml",
            )
            self.assertEqual(rows[4].attrib["OwnerRes"], "5")
            self.assertEqual(filenames[5], "NPC_0001_Mirium.model")
            self.assertEqual(rows[5].attrib["CustomInt"], "1,2")
            self.assertEqual(rows[5].attrib["Size"], str(mesh_path.stat().st_size))
            self.assertEqual(
                rows[4].attrib["Size"],
                str(materials_path.stat().st_size),
            )
