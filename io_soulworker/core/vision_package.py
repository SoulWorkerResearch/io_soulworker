"""Vision packages (`datas/SoundSystem*.vArc`).

Layout, all little endian:

    0x00  "VISIONPACKAGE\\0", u16 version
    0x10  u32 file_count, u32 names_size
    0x18  u32, u32 (equal to the largest entry size in the samples seen)
    0x20  file_count * { u16 name_len, u32 size, u32 stored_size, u32 offset }
    then  names_size bytes of NUL-terminated names
    then  file data at absolute offsets

Only uncompressed entries (`size == stored_size`) have been seen.

Run directly, because importing the `io_soulworker` package needs `bpy`:

    python -I io_soulworker/core/vision_package.py list <datas_dir>
    python -I io_soulworker/core/vision_package.py extract <datas_dir> <out_root>
"""
from __future__ import annotations

import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


MAGIC = b"VISIONPACKAGE\0"
HEADER_SIZE = 0x20
ENTRY_FORMAT = "<HIII"
ENTRY_SIZE = struct.calcsize(ENTRY_FORMAT)
COPY_CHUNK_SIZE = 1 << 20
PACKAGE_SUFFIX = ".varc"


@dataclass(frozen=True)
class VisionPackageEntry:

    name: str
    size: int
    stored_size: int
    offset: int


def _decode_name(raw: bytes) -> str:

    for encoding in ("cp949", "utf-8"):

        try:
            return raw.decode(encoding)

        except UnicodeDecodeError:
            pass

    return raw.decode("utf-8", errors="replace")


def read_entries(path: Path) -> list[VisionPackageEntry]:

    with open(path, "rb") as stream:

        header = stream.read(HEADER_SIZE)

        if len(header) != HEADER_SIZE or not header.startswith(MAGIC):
            raise ValueError(f"not a Vision package: {path}")

        count, names_size = struct.unpack_from("<II", header, 0x10)
        table = stream.read(count * ENTRY_SIZE)
        names = stream.read(names_size)

    if len(table) != count * ENTRY_SIZE or len(names) != names_size:
        raise ValueError(f"truncated table: {path}")

    file_size = path.stat().st_size
    entries = []
    position = 0

    for index in range(count):

        name_len, size, stored_size, offset = struct.unpack_from(
            ENTRY_FORMAT, table, index * ENTRY_SIZE)
        end = position + name_len

        if end >= names_size or names[end] != 0:
            raise ValueError(f"bad name {index} in {path}")

        if offset + stored_size > file_size:
            raise ValueError(f"entry {index} overruns {path}")

        entries.append(VisionPackageEntry(
            _decode_name(names[position:end]), size, stored_size, offset))
        position = end + 1

    if position != names_size:
        raise ValueError(f"names size mismatch in {path}")

    return entries


def find_packages(datas_dir: Path) -> list[Path]:
    """Packages in numeric order: SoundSystem2 before SoundSystem10."""

    found = [path for path in datas_dir.iterdir()
             if path.suffix.lower() == PACKAGE_SUFFIX]

    return sorted(found, key=lambda path: (len(path.name), path.name.lower()))


def target_path(out_root: Path, name: str) -> Path:
    """Strip `..` so a stored name stays under the unpack root."""

    parts = [part for part in name.replace("\\", "/").split("/")
             if part not in ("", ".", "..")]

    if not parts:
        raise ValueError(f"empty entry name: {name!r}")

    return out_root.joinpath(*parts)


def extract_package(path: Path, out_root: Path) -> tuple[int, int]:
    """Returns (written, skipped). A file with the expected size is skipped."""

    written = skipped = 0

    with open(path, "rb") as stream:

        for entry in read_entries(path):

            if entry.size != entry.stored_size:
                raise ValueError(f"compressed entry {entry.name} in {path}")

            target = target_path(out_root, entry.name)

            if target.is_file() and target.stat().st_size == entry.size:
                skipped += 1
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".part")
            stream.seek(entry.offset)
            left = entry.stored_size

            with open(partial, "wb") as out:

                while left:

                    data = stream.read(min(COPY_CHUNK_SIZE, left))

                    if not data:
                        raise EOFError(f"{entry.name} in {path}")

                    out.write(data)
                    left -= len(data)

            os.replace(partial, target)
            written += 1

    return written, skipped


def main(argv: list[str]) -> int:

    if len(argv) == 2 and argv[0] == "list":

        for package in find_packages(Path(argv[1])):

            for entry in read_entries(package):
                print(f"{package.name}\t{entry.size}\t{entry.name}")

        return 0

    if len(argv) == 3 and argv[0] == "extract":

        written = skipped = 0

        for package in find_packages(Path(argv[1])):

            package_written, package_skipped = extract_package(
                package, Path(argv[2]))
            written += package_written
            skipped += package_skipped

        print(f"written={written} skipped={skipped}")

        return 0

    print(__doc__, file=sys.stderr)

    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
