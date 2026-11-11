from __future__ import annotations

from logging import error
from pathlib import Path

from bpy.types import Operator

from io_soulworker.core.binary_reader import TruncatedFileError
from io_soulworker.core.vis_chunk_file import (
    ChunkReadError,
    NotVisionFileError,
)


_CUT_SHORT_HINT = (
    "The file looks cut short: unpack it from the game archive again."
)
_DAMAGED_HINT = (
    "The file is damaged, or it was made by a version of the game this "
    "add-on cannot read."
)
_NOT_VISION_HINT = (
    "Choose a .model, .vmesh or .anim file unpacked from the game."
)
_BUG_HINT = "The details are in the system console."


def describe_import_failure(path: Path, failure: BaseException) -> str:
    """Why ``path`` could not be imported, in words for the person importing.

    Names the file and what is wrong with it, and says what to do about it
    when there is something to do.
    """

    if isinstance(failure, NotVisionFileError):

        reason = f"{failure}. {_NOT_VISION_HINT}"

    elif isinstance(failure, TruncatedFileError):

        reason = f"{failure}. {_CUT_SHORT_HINT}"

    elif isinstance(failure, ChunkReadError):

        hint = (
            _CUT_SHORT_HINT
            if isinstance(failure.__cause__, TruncatedFileError)
            else _DAMAGED_HINT
        )
        reason = f"{failure}. {hint}"

    elif isinstance(failure, FileNotFoundError):

        reason = "the file does not exist."

    elif isinstance(failure, OSError):

        reason = f"the file cannot be read ({failure.strerror or failure})."

    else:

        reason = (
            f"unexpected error ({type(failure).__name__}: {failure}). "
            f"{_BUG_HINT}"
        )

    return f"Cannot import {path.name}: {reason}"


def report_import_failure(
        operator: Operator,
        path: Path,
        failure: BaseException) -> None:
    """Tell the person which file failed and why; log the details."""

    message = describe_import_failure(path, failure)

    error("%s", message, exc_info=failure)
    operator.report({"ERROR"}, message)
