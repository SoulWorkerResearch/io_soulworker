from __future__ import annotations

from collections.abc import Callable, Iterable

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


def paramstring_in_source_order(
        source: dict[str, str],
        params: Iterable[ShaderParamComment],
        value_for: Callable[[ShaderParamComment, str | None], str | None]) -> str:
    """Build a ``paramstring`` that keeps the entries and order of ``source``.

    Entries that are not PARAMCOMMENT parameters of the effect stay as they
    are. ``value_for(param, text)`` answers for a PARAMCOMMENT parameter, with
    ``text`` the value in ``source`` or ``None`` when ``source`` has none: it
    returns the text to write, or ``None`` to keep the source text (or, for a
    parameter ``source`` lacks, to leave it out). Parameters that ``source``
    lacks and ``value_for`` fills come last, in PARAMCOMMENT order.
    """

    params = list(params)
    by_name = {param.name: param for param in params}
    pairs: list[tuple[str, str]] = []

    for name, text in source.items():

        param = by_name.get(name)
        value = value_for(param, text) if param is not None else None

        pairs.append((name, text if value is None else value))

    for param in params:

        if param.name in source:

            continue

        value = value_for(param, None)

        if value is not None:

            pairs.append((param.name, value))

    return format_paramstring(pairs)


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
