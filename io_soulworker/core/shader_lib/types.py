from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ShaderParamComment:
    """One PARAMCOMMENT entry inside an EFFECT block."""

    name: str
    description: str
    default: str
    value_type: str
    ui: str


@dataclass
class ShaderEffect:
    """Parsed EFFECT block from a .ShaderLib file."""

    name: str
    params: list[ShaderParamComment] = field(default_factory=list)


@dataclass
class ShaderLibrary:
    """Parsed .ShaderLib document."""

    path: str
    stem: str
    effects: dict[str, ShaderEffect] = field(default_factory=dict)
