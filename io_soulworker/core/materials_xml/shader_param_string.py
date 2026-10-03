from __future__ import annotations

from collections.abc import Iterable

from io_soulworker.core.shader_lib.types import ShaderParamComment


def format_param_float(value: float) -> str:
    """Format a float the way Vision ``paramstring`` values are stored."""

    number = float(value)

    if number != number or number in (float("inf"), float("-inf")):

        return "0"

    rounded = round(number, 7)

    if abs(rounded - round(rounded)) < 1e-7:

        return str(int(round(rounded)))

    text = f"{rounded:.7f}".rstrip("0").rstrip(".")

    return text or "0"


def format_paramstring(pairs: Iterable[tuple[str, str]]) -> str:
    """Serialize ``name=value`` entries with a trailing semicolon."""

    parts = [f"{name}={value}" for name, value in pairs if name]

    if not parts:

        return ""

    return ";".join(parts) + ";"


def paramstring_from_params(
        params: Iterable[ShaderParamComment],
        values: dict[str, str] | None = None) -> str:
    """Build a ``paramstring`` in PARAMCOMMENT order.

    Missing names fall back to the ShaderLib default.
    """

    lookup = values or {}

    return format_paramstring(
        (param.name, lookup.get(param.name, param.default))
        for param in params
    )


class ShaderParamString(dict):
    """Parse a Vision ``paramstring`` attribute into name → raw value entries."""

    def __init__(self, line: str):

        for row in line.split(";"):

            if row == "":

                continue

            name, separator, value = row.partition("=")

            if not separator:

                continue

            self[name] = value

    def to_string(self) -> str:

        return format_paramstring(self.items())
