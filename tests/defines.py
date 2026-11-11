from __future__ import annotations

from os import getenv
from pathlib import Path


_DEFAULT_UNPACKED_RESOURCES = (
    "/run/media/sawich/acheron/SteamLibrary/steamapps/common"
    "/Soulworker_KR/_datas"
)

_MESH_SUFFIXES = (".model", ".vmesh")


class Defines:

    TEST_FILES = list(Path("tests/datas/Models").glob("*.model"))

    UNPACKED_RESOURCES = Path(
        getenv("SOULWORKER_RESOURCES", _DEFAULT_UNPACKED_RESOURCES)
    )
    """Root of the unpacked game tree. Override with ``SOULWORKER_RESOURCES``."""

    @staticmethod
    def iter_unpacked_meshes(root: Path) -> list[Path]:
        """Every ``.model`` / ``.vmesh`` below ``root``, sorted for stable runs."""

        return sorted(
            path
            for path in Path(root).rglob("*")
            if path.is_file() and path.suffix.lower() in _MESH_SUFFIXES
        )
