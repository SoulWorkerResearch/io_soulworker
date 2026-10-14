from __future__ import annotations

from pathlib import Path
from json import dumps
from os import getenv
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase
from xml.etree.ElementTree import parse

import bpy

from io_soulworker.core.binary_reader import BinaryReader
from io_soulworker.core.vis_bin_header import VisBinHeader
from io_soulworker.core.vis_chunk_id import VisChunkId
from io_soulworker.file_export.mesh_builder import build_geometry
from io_soulworker.file_export.model_exporter import (
    build_model_from_blender_object,
    write_model_file,
)
from io_soulworker.file_export.vmesh_exporter import write_vmesh_file
from io_soulworker.file_import.model.chunk_reader import ModelChunkReader
from io_soulworker.file_import.model.file_reader import ModelFileReader
from io_soulworker.file_import.runner import in_blender


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)


class TestMeshExport(TestCase):

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def tearDown(self) -> None:

        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _new_cube(self, name: str = "ExportCube"):

        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(
            [(-0.1, -0.1, 0.0), (0.1, -0.1, 0.0),
             (0.1, 0.1, 0.0), (-0.1, 0.1, 0.0)],
            [],
            [(0, 1, 2, 3)],
        )
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        return obj

    def test_export_vmesh_writes_materials_xml(self):

        obj = self._new_cube()
        with TemporaryDirectory() as temp:

            path = Path(temp) / "Cube.vmesh"
            write_vmesh_file(path, obj)

            self.assertTrue(path.is_file())
            xml_path = Path(temp) / "Cube.vmesh_data" / "materials.xml"
            resources_path = Path(temp) / "Cube.vmesh_data" / "resources.xml"
            self.assertTrue(xml_path.is_file())
            self.assertTrue(resources_path.is_file())

            with BinaryReader(path) as reader:

                header = VisBinHeader.from_reader(reader)
                self.assertEqual(header.cid, VisChunkId.VBIN)

            material = parse(xml_path).getroot().find("Materials/Material")
            self.assertIsNotNone(material)
            self.assertIn("diffuse", material.attrib)

            resources = parse(resources_path).getroot().find("Resources")
            mesh_row = resources.find(
                "Resource[@Manager='Static/Dynamic Meshes']"
            )
            self.assertEqual(mesh_row.attrib["CustomInt"], "1,1")

    def test_export_model_writes_skeleton_and_materials(self):

        mesh_obj = self._new_cube("SkinnedCube")

        armature = bpy.data.armatures.new("ExportArmature")
        armature_obj = bpy.data.objects.new("ExportArmature", armature)
        bpy.context.collection.objects.link(armature_obj)
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")
        bone = armature.edit_bones.new("Root")
        bone.head = (0.0, 0.0, 0.0)
        bone.tail = (0.0, 0.1, 0.0)
        bpy.ops.object.mode_set(mode="OBJECT")

        modifier = mesh_obj.modifiers.new("Armature", "ARMATURE")
        modifier.object = armature_obj
        group = mesh_obj.vertex_groups.new(name="Root")
        group.add([0, 1, 2, 3], 1.0, "REPLACE")

        with TemporaryDirectory() as temp:

            path = Path(temp) / "Cube.model"
            write_model_file(path, mesh_obj, armature_obj)

            self.assertTrue(path.is_file())
            self.assertTrue(
                (Path(temp) / "Cube.model_data" / "materials.xml").is_file()
            )
            self.assertTrue(
                (Path(temp) / "Cube.model_data" / "resources.xml").is_file()
            )

            with BinaryReader(path) as reader:

                header = VisBinHeader.from_reader(reader)
                self.assertEqual(header.cid, VisChunkId.VBIN)

            payload = path.read_bytes()
            self.assertIn(b"LEKS", payload)
            self.assertIn(b"THGW", payload)
            self.assertIn(b"SDNB", payload)

    def test_export_legacy_skeleton_uses_stored_native_axes(self):
        from mathutils import Vector

        obj = self._new_cube("Legacy")
        data = bpy.data.armatures.new("LegacyRig")
        arm = bpy.data.objects.new("LegacyRig", data)
        bpy.context.collection.objects.link(arm)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        bone = data.edit_bones.new("Root")
        bone.head = (0, 0, 0.2)
        bone.tail = (0.1, 0, 0.2)
        bpy.ops.object.mode_set(mode='OBJECT')
        arm["soulworker_bone_names_by_index"] = ["Root"]
        arm["soulworker_skeleton"] = dumps([{
            "name": "Root", "parent_id": -1,
            "local_position": [0, 0, 0.2],
            "local_orientation": [1, 0, 0, 0],
        }])
        skeleton = build_model_from_blender_object(obj, arm).skeleton
        bone = skeleton.bones[0]
        self.assertLess((bone.inverse_object_space_position
                         - Vector((0, 0, -20))).length, 1e-5)
        self.assertAlmostEqual(
            abs(bone.inverse_object_space_orientation.w), 1.0)

    def test_export_dynamic_mesh_uses_armature_space(self):
        from mathutils import Matrix

        obj = self._new_cube("Placed")
        data = bpy.data.armatures.new("PlacedRig")
        arm = bpy.data.objects.new("PlacedRig", data)
        bpy.context.collection.objects.link(arm)
        obj.parent = arm
        arm.matrix_world = (Matrix.Translation((3, 4, 5))
                            @ Matrix.Rotation(0.7, 4, 'Z')
                            @ Matrix.Scale(2.0, 4))
        bpy.context.view_layer.update()
        geometry = build_model_from_blender_object(obj, arm).mesh
        self.assertLess((geometry.vertices[0] / 100
                         - obj.data.vertices[0].co).length, 1e-5)

    def test_export_rebases_material_resources_for_new_directory(self):
        from io_soulworker.file_import.resource_path import resolve_resource_path

        obj = self._new_cube("Textured")
        material = bpy.data.materials.new("Textured")
        material.use_nodes = True
        obj.data.materials.append(material)
        with TemporaryDirectory() as folder:
            root = Path(folder) / "unpacked"
            textures = root / "Character/Hero/Textures"
            textures.mkdir(parents=True)
            texture = textures / "diffuse.png"
            image = bpy.data.images.new("Diffuse", width=1, height=1)
            image.filepath_raw = str(texture)
            image.file_format = 'PNG'
            image.save()
            node = material.node_tree.nodes.new('ShaderNodeTexImage')
            node.name = 'Diffuse'
            node.image = image
            material["soulworker_diffuse"] = r"Textures\diffuse.png"
            material["soulworker_shader_library"] = "Hero"
            material["soulworker_shader_effect"] = "Toon"
            material["soulworker_shader_paramstring"] = (
                r"MaskTexture=Character\Hero\Textures\diffuse.png;")
            shaders = root / "Shaders"
            shaders.mkdir()
            (shaders / "Hero.ShaderLib").write_text("<ShaderLibrary/>")
            path = Path(folder) / "export/Textured.model"
            write_model_file(path, obj, resources_root=root)
            xml = parse(path.parent / (path.name + '_data/materials.xml'))
            row = xml.getroot().find('Materials/Material')
            self.assertEqual(resolve_resource_path(
                path.parent, row.attrib['diffuse']), texture.resolve())
            shader = row.find('Shader')
            self.assertIsNotNone(shader)
            self.assertEqual(resolve_resource_path(
                path.parent, shader.attrib['library']),
                (shaders / 'Hero.ShaderLib').resolve())
            self.assertIn('MaskTexture=', shader.attrib['paramstring'])

    def test_export_real_model_preserves_bind_pose_and_resource_paths(self):
        from io_soulworker.core.materials_xml.shader_param_string import ShaderParamString
        from io_soulworker.file_import.resource_path import resolve_resource_path

        root = Path(getenv(
            'SOULWORKER_RESOURCES',
            'A:/SteamLibrary/steamapps/common/Soulworker_KR/_datas'))
        source = root / 'Character/NPC/NPC_0001_Mirium/NPC_0001_Mirium_Upper.model'
        if not source.is_file():
            self.skipTest('unpacked Mirium model unavailable')

        class SkeletonReader(ModelChunkReader):
            def on_skeleton(self, chunk):
                self.skeleton = chunk

        original = SkeletonReader(source)
        original.run()
        obj = ModelFileReader(source, bpy.context, 7.0, reuse_mesh=False).run()
        with TemporaryDirectory() as folder:
            target = Path(folder) / source.name
            write_model_file(target, obj, obj.parent, root)
            exported = SkeletonReader(target)
            exported.run()
            self.assertEqual(len(exported.skeleton.bones),
                             len(original.skeleton.bones))
            for before, after in zip(original.skeleton.bones, exported.skeleton.bones):
                self.assertEqual(before.name, after.name)
                self.assertEqual(before.parent_id, after.parent_id)
                self.assertEqual(before.inverse_object_space_position,
                                 after.inverse_object_space_position)
                self.assertEqual(before.inverse_object_space_orientation,
                                 after.inverse_object_space_orientation)
            xml = parse(target.parent / (target.name + '_data/materials.xml'))
            for material in xml.getroot().findall('Materials/Material'):
                self.assertIsNotNone(resolve_resource_path(
                    target.parent, material.attrib['diffuse']))
                shader = material.find('Shader')
                self.assertIsNotNone(shader)
                self.assertIsNotNone(resolve_resource_path(
                    target.parent, shader.attrib['library']))
                for value in ShaderParamString(shader.attrib['paramstring']).values():
                    if Path(value.replace('\\', '/')).suffix.lower() == '.dds':
                        self.assertIsNotNone(
                            resolve_resource_path(target.parent, value))

    def test_export_uses_vertex_normals_on_sharp_mesh(self):

        mesh = bpy.data.meshes.new("Corner")
        mesh.from_pydata(
            [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0),
             (0.0, 0.1, 0.0), (0.0, 0.0, 0.1)],
            [],
            [(0, 1, 2), (0, 2, 3)],
        )
        mesh.update()
        obj = bpy.data.objects.new("Corner", mesh)
        bpy.context.collection.objects.link(obj)

        geometry = build_geometry(obj)
        first = geometry.mesh.normals[geometry.mesh.indices[0]]
        second = geometry.mesh.normals[geometry.mesh.indices[1]]

        self.assertGreater(first.length, 0.9)
        self.assertGreater(abs(first.z - 1.0), 0.1)
        self.assertNotEqual(
            (round(first.x, 3), round(first.y, 3), round(first.z, 3)),
            (round(second.x, 3), round(second.y, 3), round(second.z, 3)),
        )

    def test_import_applies_file_normals(self):

        path = Path("tests/datas/Models/Sphere.model")

        if not path.is_file():

            self.skipTest(f"missing fixture: {path}")

        class _MeshReader(ModelChunkReader):

            def __init__(self, mesh_path: Path) -> None:

                super().__init__(mesh_path)
                self.chunk = None

            def on_mesh(self, chunk) -> None:

                self.chunk = chunk

        parsed = _MeshReader(path)
        parsed.run()
        self.assertIsNotNone(parsed.chunk)
        self.assertEqual(len(parsed.chunk.normals), parsed.chunk.vertex_count)
        self.assertGreater(parsed.chunk.normals[0].length, 0.9)

        ModelFileReader(path, bpy.context, 7.0, reuse_mesh=False).run()
        obj = next(item for item in bpy.data.objects if item.type == "MESH")
        self.assertTrue(obj.data.has_custom_normals)
