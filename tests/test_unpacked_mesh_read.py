from __future__ import annotations

from logging import basicConfig
from os import getenv
from pathlib import Path
from time import perf_counter
from unittest import SkipTest, TestCase

from tests.defines import Defines


_REPORT = Path("tests/unpacked_mesh_read_failures.log")
_BLENDER_HINT = (
    "run inside Blender: blender --background "
    "--factory-startup --python tests/run_in_blender.py"
)

_EDGE_CASE_MESHES = (
    Path(r"Character\Monster\MOB_0421_Lawscar\MOB_0421_Lawscar_spear.model"),
    Path(r"FXs\Mesh\FX_360D_Ray_Mesh_02_01.vmesh"),
    Path(r"World\Meshes\Cloudream\C001\C006_HH_HERO\C06_H_Basin_A_A.vmesh"),
    Path(r"World\Meshes\Cloudream\F031\RT_vehicle_ab.vmesh"),
    Path(r"World\Meshes\Cloudream\F051\CB_a1.vmesh"),
    Path(r"World\Meshes\Cloudream\F051\CB_a44.vmesh"),
    Path(r"World\Meshes\Cloudream\F051\RF_Beam.vmesh"),
)


class TestUnpackedMeshRead(TestCase):

    @classmethod
    def setUpClass(cls) -> None:

        try:
            from io_soulworker.file_import.runner import in_blender
            from tests import unpacked_mesh_read
        except ImportError as exc:
            raise SkipTest(_BLENDER_HINT) from exc

        if not in_blender():
            raise SkipTest(_BLENDER_HINT)

        cls._helpers = unpacked_mesh_read

    def test_parse_fixture_models(self) -> None:

        files = Defines.iter_unpacked_meshes(Path("tests/datas"))
        self._assert_meshes_read(
            files,
            blender_import=False,
            root=Path("tests/datas"),
        )

    def test_import_fixture_models(self) -> None:

        files = Defines.iter_unpacked_meshes(Path("tests/datas"))
        self._assert_meshes_read(
            files,
            blender_import=True,
            root=Path("tests/datas"),
        )

    def test_parse_edge_case_meshes(self) -> None:

        root = Defines.UNPACKED_RESOURCES

        if not root.is_dir():
            self.skipTest(f"unpacked resources not found: {root}")

        files = [root / relative for relative in _EDGE_CASE_MESHES]
        missing = [path for path in files if not path.is_file()]

        if missing:
            self.skipTest("edge-case meshes not found: " + ", ".join(
                str(path) for path in missing
            ))

        self._assert_meshes_read(files, blender_import=False, root=root)

    def test_parse_all_models_and_vmeshes(self) -> None:

        root = Defines.UNPACKED_RESOURCES

        if not root.is_dir():
            self.skipTest(f"unpacked resources not found: {root}")

        files = Defines.iter_unpacked_meshes(root)
        self._assert_meshes_read(files, blender_import=False, root=root)

    def test_import_all_models_and_vmeshes(self) -> None:

        if getenv("SOULWORKER_BLENDER_IMPORT") != "1":
            self.skipTest(
                "set SOULWORKER_BLENDER_IMPORT=1 to import every "
                ".model/.vmesh inside Blender"
            )

        root = Defines.UNPACKED_RESOURCES

        if not root.is_dir():
            self.skipTest(f"unpacked resources not found: {root}")

        files = Defines.iter_unpacked_meshes(root)
        self._assert_meshes_read(files, blender_import=True, root=root)

    def _assert_meshes_read(
            self,
            files: list[Path],
            *,
            blender_import: bool,
            root: Path) -> None:

        self.assertGreater(len(files), 0, "no .model/.vmesh files were found")

        helpers = self._helpers
        started = perf_counter()
        failures = helpers.read_all_meshes(
            files,
            blender_import=blender_import,
            on_progress=lambda index, total, path: helpers.log_progress(
                index, total, path, started),
        )

        if not failures:
            if _REPORT.exists():
                _REPORT.unlink()
            return

        helpers.write_failure_report(failures, _REPORT, root)
        self.fail(
            f"{len(failures)}/{len(files)} meshes failed. See {_REPORT}\n"
            f"{helpers.format_failure_summary(failures, root)}"
        )


basicConfig(
    level="INFO",
    format="[%(filename)40s():%(lineno)4s() - %(funcName)20s() ] %(message)s",
)
