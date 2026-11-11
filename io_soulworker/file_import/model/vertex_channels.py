"""Put the vertex fields of a VMSH chunk on a Blender mesh.

Every two-float texture coordinate set becomes a UV map, in slot order, so
the first set stays the active and render one. A three-float set cannot be a
UV map, so it becomes a point attribute. The colour bytes become a colour
point attribute. The vertex layout and anything the importer cannot decode
are kept as custom properties for the exporter.
"""

from __future__ import annotations

from array import array
from base64 import b64encode
from json import dumps
from logging import warning
from zlib import compress

from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.vertex_layout import (
    COLOR_ATTRIBUTE,
    LAYOUT_PROPERTY,
    MAX_UV_LAYERS,
    OPAQUE_PROPERTY,
    VertexLayoutRecord,
    flip_set_v,
    uv_layer_name,
    vector_attribute_name,
)


def _expand_to_loops(per_vertex: list, loop_vertex: array) -> list[float]:
    """Flat per-loop floats from one tuple per vertex."""

    return [component for vertex in loop_vertex
            for component in per_vertex[vertex]]


def import_vertex_channels(mesh, chunk: VMshChunk) -> None:
    """Add the file's texture sets, colour and layout record to ``mesh``.

    The mesh must hold one Blender vertex per file vertex, as ``on_mesh``
    builds it.
    """

    count = len(mesh.vertices)
    record = VertexLayoutRecord(chunk.descriptor, chunk.vertex_count)
    loop_vertex = array("i", [0]) * len(mesh.loops)
    mesh.loops.foreach_get("vertex_index", loop_vertex)

    uv_sets: list[tuple[int, list]] = []

    if chunk.uvs:

        uv_sets.append((0, [(uv[0], uv[1]) for uv in chunk.uvs]))

    vector_sets: list[tuple[int, list]] = []

    for slot, values in sorted(chunk.tex_sets.items()):

        if not values:

            continue

        if len(values[0]) == 2:

            uv_sets.append((slot, [(u, flip_set_v(v)) for u, v in values]))

        else:

            vector_sets.append((slot, values))

    for slot, values in sorted(uv_sets):

        if len(values) != count or len(mesh.uv_layers) >= MAX_UV_LAYERS:

            warning("Texture set %d is left out of mesh %s", slot, mesh.name)
            continue

        name = uv_layer_name(slot)
        layer = mesh.uv_layers.new(name=name)
        layer.uv.foreach_set("vector", _expand_to_loops(values, loop_vertex))
        record.uv_layers[slot] = layer.name

    for slot, values in vector_sets:

        if len(values) != count:

            warning("Texture set %d is left out of mesh %s", slot, mesh.name)
            continue

        attribute = mesh.attributes.new(
            vector_attribute_name(slot), "FLOAT_VECTOR", "POINT")
        attribute.data.foreach_set(
            "vector", [component for value in values for component in value])
        record.vector_attributes[slot] = attribute.name

    if len(chunk.colors) == count and count:

        attribute = mesh.color_attributes.new(
            COLOR_ATTRIBUTE, "FLOAT_COLOR", "POINT")
        attribute.data.foreach_set(
            "color", [byte / 255.0 for color in chunk.colors
                      for byte in color])
        record.color_attribute = attribute.name

    mesh[LAYOUT_PROPERTY] = record.to_json()

    if chunk.opaque:

        mesh[OPAQUE_PROPERTY] = dumps({
            name: {
                "size": len(values[0]) if values else 0,
                "data": b64encode(compress(b"".join(values))).decode("ascii"),
            }
            for name, values in chunk.opaque.items()
        })
