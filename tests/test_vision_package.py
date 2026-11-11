from __future__ import annotations

import struct
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from io_soulworker.core.vision_package import (
    ENTRY_SIZE,
    HEADER_SIZE,
    MAGIC,
    extract_package,
    find_packages,
    read_entries,
    target_path,
)


def _package_bytes(files: list[tuple[bytes, bytes]], *, stored_delta: int = 0) -> bytes:

    names = b"".join(name + b"\0" for name, _ in files)
    offset = HEADER_SIZE + len(files) * ENTRY_SIZE + len(names)
    largest = max(len(data) for _, data in files)
    header = MAGIC + struct.pack("<H", 1)
    header += struct.pack("<IIII", len(files), len(names), largest, largest)
    table = b""
    body = b""

    for name, data in files:

        size = len(data)
        table += struct.pack("<HIII", len(name), size + stored_delta, size, offset)
        body += data
        offset += size

    return header + table + names + body


class TestVisionPackage(TestCase):

    def setUp(self) -> None:

        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        self.out = self.root / "_datas"
        self.package = self.root / "SoundSystem1.vArc"

    def test_read_entries(self) -> None:

        self.package.write_bytes(_package_bytes([
            (b"Sounds/a.fev", b"RIFF"),
            (b"Sounds/b.fsb", b"FSB5data"),
        ]))

        entries = read_entries(self.package)

        self.assertEqual(
            [(e.name, e.size, e.stored_size) for e in entries],
            [("Sounds/a.fev", 4, 4), ("Sounds/b.fsb", 8, 8)],
        )
        self.assertEqual(entries[1].offset, entries[0].offset + 4)

    def test_extract_writes_content_then_skips(self) -> None:

        self.package.write_bytes(_package_bytes([
            (b"Sounds/a.fev", b"RIFF"),
            (b"Sounds/b.fsb", b"FSB5data"),
        ]))

        self.assertEqual(extract_package(self.package, self.out), (2, 0))
        self.assertEqual((self.out / "Sounds/a.fev").read_bytes(), b"RIFF")
        self.assertEqual((self.out / "Sounds/b.fsb").read_bytes(), b"FSB5data")
        self.assertEqual(list(self.out.rglob("*.part")), [])
        self.assertEqual(extract_package(self.package, self.out), (0, 2))

    def test_names_stay_under_root(self) -> None:

        self.assertEqual(
            target_path(self.out, "../bin\\..\\Table/a.res"),
            self.out / "bin" / "Table" / "a.res",
        )

        with self.assertRaises(ValueError):
            target_path(self.out, "../..")

    def test_rejects_bad_magic(self) -> None:

        self.package.write_bytes(b"NOTAPACKAGE".ljust(HEADER_SIZE, b"\0"))

        with self.assertRaises(ValueError):
            read_entries(self.package)

    def test_rejects_entry_past_end_of_file(self) -> None:

        data = _package_bytes([(b"a.fev", b"RIFF")])
        self.package.write_bytes(data[:-1])

        with self.assertRaises(ValueError):
            read_entries(self.package)

    def test_refuses_compressed_entry(self) -> None:

        self.package.write_bytes(_package_bytes(
            [(b"a.fev", b"RIFF")], stored_delta=10))

        with self.assertRaises(ValueError):
            extract_package(self.package, self.out)

    def test_find_packages_is_numeric_and_filtered(self) -> None:

        for name in ("SoundSystem10.vArc", "SoundSystem2.vArc", "data01.v"):
            (self.root / name).write_bytes(b"")

        self.assertEqual(
            [path.name for path in find_packages(self.root)],
            ["SoundSystem2.vArc", "SoundSystem10.vArc"],
        )
