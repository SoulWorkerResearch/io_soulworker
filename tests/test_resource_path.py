from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from io_soulworker.file_import.resource_path import (
    is_builtin_texture,
    resolve_resource_path,
)


class TestResolveResourcePath(TestCase):

    def setUp(self) -> None:

        self._temp = TemporaryDirectory()
        self.root = Path(self._temp.name) / "_datas"
        self.texture = self.root / "World" / "Textures" / \
            "Cloudream" / "F031" / "RT_ringer_a.dds"
        self.texture.parent.mkdir(parents=True)
        self.texture.write_bytes(b"DDS ")
        self.mesh_dir = self.root / "World" / "Meshes" / "Cloudream" / "F031"
        self.mesh_dir.mkdir(parents=True)

    def tearDown(self) -> None:

        self._temp.cleanup()

    def test_exact_and_case_insensitive_relative(self):

        self.assertEqual(
            resolve_resource_path(
                self.root, r"World\Textures\Cloudream\F031\RT_ringer_a.dds"),
            self.texture.resolve(),
        )
        self.assertEqual(
            resolve_resource_path(
                self.root, r"world\textures\cloudream\f031\rt_ringer_a.DDS"),
            self.texture.resolve(),
        )

    def test_leading_backslash_is_root_relative(self):

        self.assertEqual(
            resolve_resource_path(
                self.root, r"\World\Textures\Cloudream\f031\RT_ringer_a.dds"),
            self.texture.resolve(),
        )

    def test_absolute_path_with_parent_segments_and_wrong_case(self):

        raw = str(self.mesh_dir / ".." / ".." / ".." / "Textures" /
                  "Cloudream" / "f031" / "RT_ringer_a.dds")
        self.assertEqual(resolve_resource_path(
            self.root, raw), self.texture.resolve())
        self.assertEqual(resolve_resource_path(
            self.mesh_dir, str(self.texture)), self.texture.resolve())

    def test_missing_returns_none(self):

        self.assertIsNone(resolve_resource_path(
            self.root, r"World\Textures\nope.dds"))
        self.assertIsNone(resolve_resource_path(
            self.root, "/definitely/not/here.dds"))
        self.assertIsNone(resolve_resource_path(self.root, ""))

    def test_builtin_textures(self):

        self.assertTrue(is_builtin_texture(r"\PlainWhite.DDS"))
        self.assertTrue(is_builtin_texture("Textures/plainwhite.dds"))
        self.assertFalse(is_builtin_texture(r"Textures\white.dds"))
