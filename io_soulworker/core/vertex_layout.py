"""The vertex layout a mesh was imported with, kept on the Blender mesh.

The importer writes it as the ``soulworker_vertex_layout`` custom property
and the exporter reads it back, so a mesh that was not edited in structure
leaves with the same descriptor and stride it arrived with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from json import JSONDecodeError, dumps, loads
from logging import warning

from io_soulworker.core.vis_vertex_descriptor import VisMBVertexDescriptor_cl


LAYOUT_PROPERTY = "soulworker_vertex_layout"
OPAQUE_PROPERTY = "soulworker_vertex_opaque"
COLOR_ATTRIBUTE = "Color"

MAX_UV_LAYERS = 8
"""Blender refuses a ninth UV map."""


def uv_layer_name(slot: int) -> str:
    """The first set keeps Blender's own name; the others carry their slot."""

    return "UVMap" if slot == 0 else "UVMap_%d" % slot


def vector_attribute_name(slot: int) -> str:
    """Name of the point attribute that holds a three-float texture set."""

    return "sw_tex%d" % slot


def flip_set_v(value: float) -> float:
    """V of a texture set after the first, between the file and Blender.

    The first set keeps negating V, so it lands in the tile below the image.
    The other sets are mostly lightmap or detail coordinates, and a lightmap
    has to stay inside 0..1 for Blender to bake into it: ``1 - v`` does that,
    and it is its own inverse.
    """

    return 1.0 - value


@dataclass
class VertexLayoutRecord:
    """The descriptor words plus the Blender names of the data they became."""

    descriptor: VisMBVertexDescriptor_cl
    vertex_count: int
    uv_layers: dict[int, str] = field(default_factory=dict)
    vector_attributes: dict[int, str] = field(default_factory=dict)
    color_attribute: str | None = None

    def to_json(self) -> str:

        return dumps({
            "descriptor": self.descriptor.to_record(),
            "vertex_count": self.vertex_count,
            "uv_layers": {str(slot): name
                          for slot, name in self.uv_layers.items()},
            "vector_attributes": {
                str(slot): name
                for slot, name in self.vector_attributes.items()},
            "color_attribute": self.color_attribute,
        })

    @classmethod
    def from_json(cls, text: str) -> 'VertexLayoutRecord | None':
        """Parse what ``to_json`` wrote; ``None`` (and a warning) otherwise."""

        try:

            payload = loads(text)
            color = payload["color_attribute"]

            return cls(
                VisMBVertexDescriptor_cl.from_record(payload["descriptor"]),
                int(payload["vertex_count"]),
                {int(slot): str(name)
                 for slot, name in payload["uv_layers"].items()},
                {int(slot): str(name)
                 for slot, name in payload["vector_attributes"].items()},
                None if color is None else str(color),
            )

        except (JSONDecodeError, KeyError, TypeError, ValueError,
                AttributeError):

            warning("The recorded vertex layout is unreadable and is ignored")
            return None
