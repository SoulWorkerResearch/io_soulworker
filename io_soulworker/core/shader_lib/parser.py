from __future__ import annotations

import re
from pathlib import Path

from io_soulworker.core.shader_lib.types import (
    ShaderEffect,
    ShaderLibrary,
    ShaderParamComment,
)

_EFFECT_START = re.compile(r"^EFFECT\s+(\S+)\s*\{", re.MULTILINE)
_PARAMCOMMENT = re.compile(
    r'PARAMCOMMENT=\{"([^"]*)","([^"]*)","([^"]*)",'
    r"([A-Za-z0-9_]+),([A-Za-z0-9_]+),\"([^\"]*)\"\}"
)


def _extract_block_body(text: str, brace_open_index: int) -> str:
    """Return text inside ``{...}`` starting at ``brace_open_index``."""

    depth = 0

    for index in range(brace_open_index, len(text)):

        char = text[index]

        if char == "{":

            depth += 1

        elif char == "}":

            depth -= 1

            if depth == 0:

                return text[brace_open_index + 1: index]

    return ""


def parse_shader_lib_text(
        text: str,
        *,
        path: str = "",
        stem: str = "") -> ShaderLibrary:
    """Parse EFFECT / PARAMCOMMENT declarations from ShaderLib source text."""

    library = ShaderLibrary(path=path, stem=stem)

    for match in _EFFECT_START.finditer(text):

        brace_index = text.find("{", match.start())

        if brace_index < 0:

            continue

        body = _extract_block_body(text, brace_index)
        effect = ShaderEffect(name=match.group(1))

        for param_match in _PARAMCOMMENT.finditer(body):

            effect.params.append(
                ShaderParamComment(
                    name=param_match.group(1),
                    description=param_match.group(2),
                    default=param_match.group(3),
                    value_type=param_match.group(4),
                    ui=param_match.group(5),
                )
            )

        library.effects[effect.name] = effect

    return library


def parse_shader_lib_file(path: Path) -> ShaderLibrary:
    """Read and parse a ``.ShaderLib`` file (cp949, same as other game text)."""

    text = path.read_text(encoding="cp949", errors="replace")

    return parse_shader_lib_text(
        text,
        path=str(path),
        stem=path.stem,
    )


def scan_shader_libs(resources_root: Path) -> list[ShaderLibrary]:
    """Scan ``{resources}/Shaders/*.ShaderLib`` and parse each library."""

    shaders_dir = resources_root / "Shaders"

    if not shaders_dir.is_dir():

        return []

    libraries: list[ShaderLibrary] = []

    for path in sorted(shaders_dir.glob("*.ShaderLib")):

        if path.is_file():

            libraries.append(parse_shader_lib_file(path))

    return libraries
