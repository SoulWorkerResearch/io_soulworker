from __future__ import annotations

from pathlib import Path
from shutil import copyfile
from struct import pack, pack_into, unpack_from
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase
from unittest.mock import patch

import bpy
from mathutils import Matrix, Quaternion, Vector

from io_soulworker import viewport_resources_panel
from io_soulworker.chunks.skel_chunk import (
    VisSkeletalBone_cl,
    VisSkeletonChunk_cl,
)
from io_soulworker.file_import import armature_builder
from io_soulworker.file_import.model import file_reader
from io_soulworker.file_import.model.file_reader import (
    ModelFileReader,
    clear_mesh_cache,
    mesh_cache_key,
)
from io_soulworker.file_import.resource_path import load_blender_image
from io_soulworker.file_import.runner import FileImportRunner, in_blender
from io_soulworker.viewport_resources_panel import (
    IO_SOULWORKER_OT_open_resource,
    register_unpack_resources_props,
    unregister_unpack_resources_props,
)


_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_BOX = Path("tests/datas/Models/Primitive_Box.model").resolve()
_OTHER_BOX = Path("tests/datas/Models/Primitive_Cylinder.model").resolve()
_BALL = Path("tests/datas/Models/MagicBall.model").resolve()
_BROKEN_LENGTH = 12600 + 40
"""The ball cut 40 bytes into its surface chunk, after the mesh was read."""


def _chunk_ranges(data: bytes) -> dict[str, tuple[int, int]]:
    """Where the data of every top-level chunk starts and how long it is."""

    from io_soulworker.core.vis_chunk_id import VisChunkId

    ranges: dict[str, tuple[int, int]] = {}
    position = 8

    while unpack_from("<i", data, position)[0] >= 0:

        chunk, length = unpack_from("<iI", data, position + 4)
        ranges.setdefault(VisChunkId.get_name(chunk), (position + 12, length))
        position += 12 + length + 8

    return ranges


class TestReadErrors(TestCase):
    """What a user sees when a file is cut short, or is not a Vision file."""

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def test_short_read_says_the_file_ended_and_where(self):

        from io_soulworker.core.binary_reader import (
            BinaryReader,
            TruncatedFileError,
        )

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Short.bin"
            # One whole number, half of a second one, then a string that
            # claims more bytes than the file has.
            path.write_bytes(pack("<IH", 7, 1))
            long_string = Path(folder) / "String.bin"
            long_string.write_bytes(pack("<I", 100) + b"abc")

            with BinaryReader(path) as reader:

                self.assertEqual(reader.read_uint32(), 7)

                with self.assertRaises(TruncatedFileError) as number:
                    reader.read_uint32()

            with BinaryReader(long_string) as reader:

                with self.assertRaises(TruncatedFileError) as string:
                    reader.read_utf8_uint32_string()

        self.assertIsInstance(number.exception, EOFError)
        self.assertEqual(number.exception.offset, 4)
        self.assertIn("ends early", str(number.exception))
        self.assertIn("offset 4", str(number.exception))
        self.assertEqual(string.exception.offset, 4)

    def test_a_file_that_is_not_a_vision_file_is_rejected(self):

        from io_soulworker.core.vis_chunk_file import NotVisionFileError
        from io_soulworker.file_import.model.chunk_reader import (
            ModelChunkReader,
        )

        with TemporaryDirectory() as folder:

            for name, content in (
                ("Empty.model", b""),
                ("Short.model", b"VB"),
                ("Foreign.model", b"RIFF" + bytes(64)),
            ):

                path = Path(folder) / name
                path.write_bytes(content)

                with self.subTest(name), self.assertRaises(
                        NotVisionFileError) as raised:
                    ModelChunkReader(path).run()

                self.assertIn("VBIN", str(raised.exception))

    def test_a_chunk_that_runs_past_the_end_names_the_chunk(self):

        from io_soulworker.core.binary_reader import TruncatedFileError
        from io_soulworker.file_import.model.chunk_reader import (
            ModelChunkReader,
        )

        data = _BOX.read_bytes()
        start, length = _chunk_ranges(data)["MTRS"]

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Cut.model"
            path.write_bytes(data[:start + length // 2])

            with self.assertRaises(TruncatedFileError) as raised:
                ModelChunkReader(path).run()

        self.assertIn("MTRS", str(raised.exception))
        self.assertEqual(raised.exception.offset, start)

    def test_a_chunk_the_parser_rejects_names_the_chunk(self):

        from io_soulworker.core.vis_chunk_file import ChunkReadError
        from io_soulworker.core.vis_chunk_id import VisChunkId
        from io_soulworker.file_import.model.chunk_reader import (
            ModelChunkReader,
        )

        data = bytearray(_BOX.read_bytes())
        start, _ = _chunk_ranges(data)["MTRS"]

        # The surface count comes first, then the header of the first
        # surface. Break the id of that surface.
        pack_into("<i", data, start + 4 + 4, 0x12345678)

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Corrupt.model"
            path.write_bytes(data)

            with self.assertRaises(ChunkReadError) as raised:
                ModelChunkReader(path).run()

        self.assertEqual(raised.exception.chunk, VisChunkId.MTRS)
        self.assertIsInstance(raised.exception.__cause__, AssertionError)
        self.assertIn("unsupported or corrupt MTRS chunk",
                      str(raised.exception))

    def test_leaving_a_chunk_does_not_hide_the_error_of_a_cut_file(self):

        from io_soulworker.core.binary_reader import BinaryReader
        from io_soulworker.core.vis_chunk_id import VisChunkId
        from io_soulworker.core.vis_chunk_reader_scope import (
            VisChunkReaderScope,
        )

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Cut.bin"
            path.write_bytes(pack("<iiI", 0, VisChunkId.VMSH, 100))

            with BinaryReader(path) as reader:

                scope = VisChunkReaderScope(reader)
                scope.depth = 0
                scope.chunk = VisChunkId.VMSH
                scope.offset = 12
                scope.length = 100

                # The chunk claims 100 bytes the file does not have, so
                # finding its end fails as well. The caller must still get
                # the error that ended the chunk.
                original = ValueError("raised inside the chunk")

                self.assertFalse(
                    scope.__exit__(ValueError, original, None))


def _inventory() -> dict[str, list[str]]:
    """Names of what an import can add, and of the objects in the scene."""

    data = bpy.data

    return {
        "objects": sorted(item.name for item in data.objects),
        "meshes": sorted(item.name for item in data.meshes),
        "armatures": sorted(item.name for item in data.armatures),
        "materials": sorted(item.name for item in data.materials),
        "images": sorted(item.name for item in data.images),
        "collections": sorted(item.name for item in data.collections),
        "in scene": sorted(item.name for item in bpy.context.scene.objects),
    }


def _skeleton() -> VisSkeletonChunk_cl:

    chunk = VisSkeletonChunk_cl()
    world = Matrix.Identity(4)

    for index, (name, position) in enumerate([
        ("Root", (0.0, 0.0, 0.0)),
        ("Arm", (20.0, 0.0, 0.0)),
    ]):

        bone = VisSkeletalBone_cl()
        bone.id = index
        bone.name = name
        bone.parent_id = index - 1
        bone.local_space_position = Vector(position)
        bone.local_space_orientation = Quaternion()
        world = world @ Matrix.Translation(position)
        inverse = world.inverted()
        bone.inverse_object_space_position = inverse.translation
        bone.inverse_object_space_orientation = inverse.to_quaternion()
        chunk.bones.append(bone)

    return chunk


class TestFailedModelImport(TestCase):
    """A model that fails to import leaves nothing of itself in the file."""

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def setUp(self) -> None:

        clear_mesh_cache()

    def tearDown(self) -> None:

        clear_mesh_cache()
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _import(self, path: Path):

        return ModelFileReader(path, bpy.context, 7.0).run()

    def _cut_ball(self, folder: str, length: int) -> Path:
        """The ball, cut to ``length`` bytes, with the texture it names."""

        path = Path(folder) / "Ball.model"
        path.write_bytes(_BALL.read_bytes()[:length])
        copyfile(_BALL.parent / "blubber.dds", Path(folder) / "blubber.dds")

        return path

    def _import_cut_ball(self, path: Path):
        """Import ``path``, which must fail. Return the surfaces and textures
        the import had read by then."""

        surfaces = []
        textures = []
        read_surface = ModelFileReader.on_surface

        def on_surface(reader, chunk):

            surfaces.append(chunk)
            return read_surface(reader, chunk)

        def load_texture(image_path):

            textures.append(load_blender_image(image_path))
            return textures[-1]

        with patch.object(ModelFileReader, "on_surface", on_surface), \
                patch.object(
                    file_reader, "load_blender_image", load_texture), \
                self.assertRaises(Exception):
            self._import(path)

        return surfaces, textures

    def test_a_failed_import_removes_what_it_created(self):

        data = _BALL.read_bytes()
        start, length = _chunk_ranges(data)["SMSH"]

        # Cut inside the chunk that follows the mesh and its surface, and
        # inside the closing marker of the file.
        for cut in (start + length // 2, len(data) - 1):

            with self.subTest(cut=cut), TemporaryDirectory() as folder:

                path = self._cut_ball(folder, cut)
                before = _inventory()

                surfaces, textures = self._import_cut_ball(path)

                # The import got as far as a surface with its texture.
                self.assertEqual(len(surfaces), 1)
                self.assertEqual(len(textures), 1)
                self.assertIsNotNone(textures[0])

                self.assertEqual(_inventory(), before)

    def test_a_failed_import_keeps_what_was_there_before(self):

        with TemporaryDirectory() as folder:

            path = self._cut_ball(folder, len(_BALL.read_bytes()) - 1)
            survivor = self._import(_BOX)
            bpy.data.materials.new("Unused")

            # The cut file names an image that is already loaded.
            loaded = bpy.data.images.load(str(Path(folder) / "blubber.dds"))
            before = _inventory()

            surfaces, textures = self._import_cut_ball(path)

            self.assertEqual(textures, [loaded])
            self.assertEqual(_inventory(), before)
            self.assertIn(survivor.name, bpy.context.scene.objects)
            self.assertEqual(
                [item.name for item in survivor.data.materials], ["Default"])

    def test_a_failed_import_keeps_a_mesh_shared_with_earlier_imports(self):

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Box.model"
            copyfile(_BOX, path)

            first = self._import(path)
            mesh = first.data
            before = _inventory()

            # The second import reuses the cached mesh and fails after it
            # made its own object.
            with patch.object(
                    ModelFileReader, "_link_object",
                    side_effect=RuntimeError("cannot link")), \
                    self.assertRaises(RuntimeError):
                self._import(path)

            self.assertEqual(_inventory(), before)
            self.assertIs(first.data, mesh)
            self.assertEqual(mesh.users, 1)
            self.assertIs(self._import(path).data, mesh)

    def test_a_failed_import_does_not_leave_its_mesh_in_the_cache(self):

        with TemporaryDirectory() as folder:

            path = Path(folder) / "Box.model"
            copyfile(_BOX, path)

            # Every chunk is read and the mesh is cached; placing the object
            # is what fails.
            with patch.object(
                    ModelFileReader, "_apply_transform",
                    side_effect=RuntimeError("cannot place")), \
                    self.assertRaises(RuntimeError):
                self._import(path)

            self.assertNotIn(mesh_cache_key(path), file_reader._MESH_CACHE)

    def _import_with_armature_then_fail(self, path: Path):
        """Read a static model, give it the skeleton, then fail."""

        def finish(reader):

            reader.on_skeleton(_skeleton())
            raise RuntimeError("cannot finish the mesh")

        with patch.object(ModelFileReader, "_finish_mesh", finish), \
                self.assertRaises(RuntimeError):
            self._import(path)

    def test_a_failed_import_removes_the_armature_it_built(self):

        survivor = self._import(_OTHER_BOX)
        bpy.context.view_layer.objects.active = survivor
        before = _inventory()

        self._import_with_armature_then_fail(_BOX)

        self.assertEqual(_inventory(), before)
        self.assertIs(bpy.context.view_layer.objects.active, survivor)

    def test_a_failure_in_edit_mode_returns_to_object_mode(self):

        survivor = self._import(_OTHER_BOX)
        before = _inventory()

        # The first bone is placed while the new armature is in edit mode.
        with patch.object(
                armature_builder.BoneHelper, "apply_rest_transform",
                side_effect=RuntimeError("cannot place the bone")):
            self._import_with_armature_then_fail(_BOX)

        self.assertEqual(_inventory(), before)
        self.assertEqual(bpy.context.mode, "OBJECT")
        self.assertIn(survivor.name, bpy.context.scene.objects)


class TestImportOperators(TestCase):
    """The operators report a file that fails and carry on with the rest."""

    @classmethod
    def setUpClass(cls) -> None:

        if not in_blender():

            raise SkipTest(_BLENDER_HINT)

    def setUp(self) -> None:

        clear_mesh_cache()

        patcher = patch.object(
            viewport_resources_panel, "sync_shader_node_groups",
            return_value=0)
        patcher.start()
        self.addCleanup(patcher.stop)

        register_unpack_resources_props()

    def tearDown(self) -> None:

        unregister_unpack_resources_props()
        clear_mesh_cache()
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _run(self, operator, **arguments) -> tuple[set[str], list[str]]:
        """Run ``operator``; return its result and the errors it reported.

        Blender hands the errors an operator reported to the script that called
        it, as one ``RuntimeError``.
        """

        returned = []

        class Run(operator):

            def execute(self, context):

                returned.append(super().execute(context))

                return returned[-1]

        module, name = operator.bl_idname.split(".")
        errors: list[str] = []

        bpy.utils.register_class(Run)

        try:

            getattr(getattr(bpy.ops, module), name)(**arguments)

        except RuntimeError as exc:

            errors = [
                line.removeprefix("Error: ")
                for line in str(exc).splitlines()
                if line.startswith("Error: ")
            ]

        finally:

            bpy.utils.unregister_class(Run)

        return returned[0], errors

    def _import_files(self, folder: str, *names: str, **options):

        return self._run(
            FileImportRunner,
            filepath=str(Path(folder) / names[0]),
            files=[{"name": name} for name in names],
            **options,
        )

    def _write_good_and_broken(self, folder: str) -> None:
        """Two good models, and one with its end cut off, in ``folder``."""

        copyfile(_BOX, Path(folder) / "First.model")
        copyfile(_OTHER_BOX, Path(folder) / "Last.model")
        (Path(folder) / "Broken.model").write_bytes(
            _BALL.read_bytes()[:_BROKEN_LENGTH])

    def test_one_bad_file_does_not_stop_a_multi_file_import(self):

        with TemporaryDirectory() as folder:

            self._write_good_and_broken(folder)

            result, errors = self._import_files(
                folder, "First.model", "Broken.model", "Last.model")

        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(
            sorted(item.name for item in bpy.context.scene.objects),
            ["First", "Last"])
        self.assertEqual(len(bpy.data.objects), 2)
        self.assertEqual(len(errors), 1)
        self.assertIn("Broken.model", errors[0])

    def test_nothing_imported_cancels_and_changes_nothing(self):

        bpy.context.scene.render.engine = "CYCLES"

        with TemporaryDirectory() as folder:

            self._write_good_and_broken(folder)
            before = _inventory()

            result, errors = self._import_files(
                folder, "Broken.model", is_create_collection=True)

        self.assertEqual(result, {"CANCELLED"})
        self.assertEqual(_inventory(), before)
        self.assertEqual(bpy.context.scene.render.engine, "CYCLES")
        self.assertEqual(len(errors), 1)

    def test_the_message_names_the_file_and_what_is_wrong(self):

        data = _BOX.read_bytes()
        start, _ = _chunk_ranges(data)["MTRS"]
        corrupt = bytearray(data)
        pack_into("<i", corrupt, start + 4 + 4, 0x12345678)

        variants = {
            "Cut.model": (data[:start + 20], "ends early"),
            "Foreign.model": (b"RIFF" + bytes(64), "VBIN"),
            "Foreign.anim": (b"RIFF" + bytes(64), "VBIN"),
            "Corrupt.model": (
                bytes(corrupt), "unsupported or corrupt MTRS chunk"),
        }

        with TemporaryDirectory() as folder:

            for name, (content, wording) in variants.items():

                (Path(folder) / name).write_bytes(content)

                with self.subTest(name):

                    _, errors = self._import_files(folder, name)

                    self.assertEqual(len(errors), 1)
                    self.assertIn(name, errors[0])
                    self.assertIn(wording, errors[0])
                    self.assertNotIn("Traceback", errors[0])

    def test_open_resource_leaves_no_collections_after_a_failure(self):

        bpy.context.scene.render.engine = "CYCLES"
        root = Path("tests/datas").resolve()
        bpy.context.scene.soulworker_unpack_resources = str(root)
        previous = bpy.context.view_layer.active_layer_collection

        with TemporaryDirectory(dir=root) as folder:

            # Below the resources root, so the collections are made first.
            path = Path(folder) / "Broken.model"
            path.write_bytes(_BALL.read_bytes()[:_BROKEN_LENGTH])
            before = _inventory()

            result, errors = self._run(
                IO_SOULWORKER_OT_open_resource, filepath=str(path))

        self.assertEqual(result, {"CANCELLED"})
        self.assertEqual(_inventory(), before)
        self.assertEqual(bpy.context.view_layer.active_layer_collection,
                         previous)
        self.assertEqual(bpy.context.scene.render.engine, "CYCLES")
        self.assertEqual(len(errors), 1)
        self.assertIn("Broken.model", errors[0])

    def test_the_file_browser_lists_only_the_files_it_imports(self):

        bpy.utils.register_class(FileImportRunner)

        try:

            properties = getattr(bpy.ops.io_soulworker, "import") \
                .get_rna_type().properties

            self.assertEqual(
                properties["filter_glob"].default, "*.model;*.vmesh;*.anim")
            self.assertTrue(properties["filter_glob"].is_hidden)

        finally:

            bpy.utils.unregister_class(FileImportRunner)
