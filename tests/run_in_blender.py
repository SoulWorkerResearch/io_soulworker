from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ADDON_ROOT = Path(__file__).resolve().parents[1]


def _argv_after_separator() -> list[str]:

    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1:]

    return []


def main() -> int:

    os.chdir(ADDON_ROOT)

    if str(ADDON_ROOT) not in sys.path:
        sys.path.insert(0, str(ADDON_ROOT))

    extra = _argv_after_separator()
    argv = [sys.argv[0], *extra] if extra else [
        sys.argv[0],
        "discover",
        "-s",
        str(ADDON_ROOT / "tests"),
        "-v",
    ]

    running = unittest.main(module=None, argv=argv, exit=False)

    return 0 if running.result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
