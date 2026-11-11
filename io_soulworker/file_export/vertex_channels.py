"""Decide which vertex fields an export writes and read them off a Blender mesh.

A mesh the importer made carries the layout it arrived with
(``soulworker_vertex_layout``), and the export writes that layout back:
the same fields at the same offsets in the same stride. Fields the mesh no
longer has are dropped with a warning and the rest are packed tightly. A mesh
made in Blender gets position, normal, one UV map for each UV layer and the
colour attribute, one after another.
"""

from __future__ import annotations

from array import array
from base64 import b64decode
from binascii import Error as Base64Error
from json import JSONDecodeError, loads
from logging import warning
from math import isnan
from zlib import decompress
from zlib import error as ZlibError

from mathutils import Vector

from io_soulworker.chunks.vmsh_chunk import VMshChunk
from io_soulworker.core.vertex_layout import (
    LAYOUT_PROPERTY,
    OPAQUE_PROPERTY,
    VertexLayoutRecord,
    flip_set_v,
)
from io_soulworker.core.vis_vertex_descriptor import (
    VertexComponent,
    VisMBVertexDescriptor_cl,
    known_size,
)


_Descriptor = VisMBVertexDescriptor_cl

_COLOR_TYPES = ("FLOAT_COLOR", "BYTE_COLOR")


def _component(kind: str, slot: int, code: int) -> VertexComponent:
    """A field of a known format, not placed yet."""

    size = known_size(kind, code)
    name = kind if kind != _Descriptor.KIND_TEXTURE else "tex%d" % slot

    return VertexComponent(name, kind, slot, code, 0, size, True)


def place_components(
        components: list[VertexComponent],
        template: VisMBVertexDescriptor_cl | None = None,
) -> VisMBVertexDescriptor_cl:
    """A descriptor that lays the fields out one after another, tightly."""

    descriptor = _Descriptor()
    descriptor.header_size = 48
    descriptor.first_text_coord = 255
    descriptor.last_text_coord = 0

    if template is not None:

        descriptor.header_size = template.header_size
        descriptor.first_text_coord = template.first_text_coord
        descriptor.last_text_coord = template.last_text_coord
        descriptor.hash = template.hash

    offset = 0

    for field in components:

        word = _Descriptor.make_offset(offset, field.code)
        offset += field.size

        match field.kind:

            case _Descriptor.KIND_POSITION:
                descriptor.pos_offset = word

            case _Descriptor.KIND_NORMAL:
                descriptor.normal_offset = word

            case _Descriptor.KIND_COLOR:
                descriptor.color_offset = word

            case _Descriptor.KIND_SECONDARY_COLOR:
                descriptor.secondary_color_offset = word

            case _:
                descriptor.tex_offset[field.slot] = word

    descriptor.stride = offset

    return descriptor


def _float_array(collection, name: str, width: int) -> array:

    values = array("f", [0.0]) * (len(collection) * width)
    collection.foreach_get(name, values)

    return values


def _attribute_reader(attribute, width: int, name: str):
    """``read(loop_index, vertex_index)`` for a point or corner attribute.

    ``None`` when the attribute is on another domain.
    """

    values = _float_array(attribute.data, name, width)

    if attribute.domain == "POINT":

        return lambda loop_index, vertex_index: tuple(
            values[vertex_index * width: vertex_index * width + width])

    if attribute.domain == "CORNER":

        return lambda loop_index, vertex_index: tuple(
            values[loop_index * width: loop_index * width + width])

    return None


def _to_byte(channel: float) -> int:
    """A colour channel as a byte; NaN and anything out of range are clamped."""

    return int(min(255.0, max(0.0, channel * 255.0)) + 0.5)


def _color_reader(attribute):
    """``read(loop_index, vertex_index)`` giving four colour bytes."""

    if attribute is None or attribute.data_type not in _COLOR_TYPES:

        return None

    # The bytes of a byte colour are what the file stores; its linear
    # ``color`` is converted from them. A float colour is kept as is.
    name = "color_srgb" if attribute.data_type == "BYTE_COLOR" else "color"
    read = _attribute_reader(attribute, 4, name)

    if read is None:

        return None

    return lambda loop_index, vertex_index: tuple(
        _to_byte(channel) for channel in read(loop_index, vertex_index))


def _uv_reader(layer):
    """``read(loop_index, vertex_index)`` giving ``(u, v)``; zeros without a layer."""

    if layer is None:

        return lambda loop_index, vertex_index: (0.0, 0.0)

    values = _float_array(layer.uv, "vector", 2)

    return lambda loop_index, vertex_index: (
        values[loop_index * 2], values[loop_index * 2 + 1])


def _opaque_bytes(mesh, name: str, size: int, record: VertexLayoutRecord):
    """The bytes the importer kept for a field it could not decode, if usable."""

    if len(mesh.vertices) != record.vertex_count:

        return None

    try:

        entry = loads(mesh[OPAQUE_PROPERTY])[name]
        raw = decompress(b64decode(entry["data"]))

        if int(entry["size"]) != size or len(raw) != size * len(mesh.vertices):

            return None

        return raw

    except (KeyError, TypeError, ValueError, JSONDecodeError, Base64Error,
            ZlibError):

        return None


def _bytes_reader(raw: bytes, size: int):
    """``read(loop_index, vertex_index)`` giving the bytes of one vertex."""

    return lambda loop_index, vertex_index: raw[
        vertex_index * size: vertex_index * size + size]


class VertexChannels:
    """The fields an export writes besides position and normal.

    ``corner`` reads them for one corner of a triangle, ``key`` makes the
    part of a vertex key that stands for them, and ``apply`` stores the
    values of the exported vertices on the chunk.

    ``keeps_vertices`` is set for a mesh that carries the layout it was
    imported with: its Blender vertices are the vertices of the file, so
    none of them may be merged into another one, not even when two of them
    agree on every field (shipped meshes hold such twins).
    """

    def __init__(
            self,
            descriptor: VisMBVertexDescriptor_cl,
            keeps_vertices: bool = False) -> None:

        self.descriptor = descriptor
        self.keeps_vertices = keeps_vertices
        self.fields: list[tuple[VertexComponent, object]] = []

    def corner(self, loop_index: int, vertex_index: int) -> tuple:

        return tuple(read(loop_index, vertex_index)
                     for _, read in self.fields)

    @staticmethod
    def key(values: tuple) -> tuple:
        """Values rounded the way a vertex key compares them; NaN equals NaN."""

        return tuple(
            tuple(None if isnan(item) else round(item, 6) for item in value)
            if isinstance(value, tuple) and value
            and isinstance(value[0], float) else value
            for value in values)

    def apply(self, chunk: VMshChunk, values: list[tuple]) -> None:
        """Store the field values of the exported vertices, in vertex order."""

        chunk.descriptor = self.descriptor
        chunk.uvs = []
        chunk.colors = []
        chunk.tex_sets = {}
        chunk.opaque = {}

        for position, (field, _) in enumerate(self.fields):

            column = [value[position] for value in values]

            if not field.known:

                chunk.opaque[field.name] = column

            elif field.kind == _Descriptor.KIND_COLOR:

                chunk.colors = column

            elif field.slot == 0 and field.size == 8:

                chunk.uvs = [Vector(uv) for uv in column]

            elif field.size == 8:

                chunk.tex_sets[field.slot] = [
                    (u, flip_set_v(v)) for u, v in column]

            else:

                chunk.tex_sets[field.slot] = column


def default_components(
        color: bool = False, uv_sets: int = 1) -> list[VertexComponent]:
    """Position, normal, an optional colour and ``uv_sets`` two-float sets."""

    components = [
        _component(_Descriptor.KIND_POSITION, 0, _Descriptor.FORMAT_FLOAT3),
        _component(_Descriptor.KIND_NORMAL, 0, _Descriptor.FORMAT_FLOAT3),
    ]

    if color:

        components.append(_component(
            _Descriptor.KIND_COLOR, 0, _Descriptor.FORMAT_BYTES4))

    components.extend(
        _component(_Descriptor.KIND_TEXTURE, slot, _Descriptor.FORMAT_FLOAT2)
        for slot in range(uv_sets))

    return components


def _blender_made_channels(mesh) -> VertexChannels:
    """Position, normal, the colour attribute and a UV map per UV layer."""

    active = mesh.uv_layers.active
    layers = ([active] if active is not None else []) + [
        layer for layer in mesh.uv_layers if layer != active]
    color = mesh.color_attributes.active_color

    if color is None and len(mesh.color_attributes):

        color = mesh.color_attributes[0]

    color_read = _color_reader(color)

    if len(layers) > _Descriptor.MAX_TEXTURES:

        warning("Only the first %d UV layers of %s are exported",
                _Descriptor.MAX_TEXTURES, mesh.name)
        layers = layers[:_Descriptor.MAX_TEXTURES]

    # A mesh without a UV map still gets the first set, zeroed.
    components = default_components(color_read is not None, len(layers) or 1)
    readers = [None, None]

    if color_read is not None:

        readers.append(color_read)

    readers.extend(_uv_reader(layer) for layer in layers or [None])

    channels = VertexChannels(place_components(components))
    channels.fields = [
        (field, read) for field, read in zip(components, readers)
        if read is not None]

    return channels


def _recorded_channels(
        mesh, record: VertexLayoutRecord) -> VertexChannels | None:
    """The layout the importer recorded, minus the fields the mesh lost."""

    readers: dict[str, object] = {}
    kept: list[VertexComponent] = []
    dropped: list[str] = []

    for field in record.descriptor.components():

        read = None
        usable = True

        if field.kind in (_Descriptor.KIND_POSITION, _Descriptor.KIND_NORMAL):

            pass

        elif not field.known:

            raw = _opaque_bytes(mesh, field.name, field.size, record)
            read = _bytes_reader(raw, field.size) if raw else None
            usable = read is not None

        elif field.kind == _Descriptor.KIND_COLOR:

            attribute = mesh.attributes.get(record.color_attribute or "")
            read = _color_reader(attribute)
            usable = read is not None

        elif field.size == 8:

            layer = mesh.uv_layers.get(record.uv_layers.get(field.slot, ""))

            if layer is None and field.slot == 0:

                layer = mesh.uv_layers.active

            usable = layer is not None
            read = _uv_reader(layer) if usable else None

        else:

            attribute = mesh.attributes.get(
                record.vector_attributes.get(field.slot, ""))
            read = (_attribute_reader(attribute, 3, "vector")
                    if attribute is not None
                    and attribute.data_type == "FLOAT_VECTOR" else None)
            usable = read is not None

        if usable:

            kept.append(field)
            readers[field.name] = read

        else:

            dropped.append(field.name)

    if not kept:

        return None

    if dropped:

        warning(
            "Mesh %s no longer has %s; the export leaves those fields out",
            mesh.name, ", ".join(dropped))
        descriptor = place_components(kept, record.descriptor)

    else:

        descriptor = record.descriptor

    channels = VertexChannels(descriptor, keeps_vertices=True)
    channels.fields = [
        (field, readers[field.name]) for field in kept
        if readers[field.name] is not None]

    return channels


def plan_vertex_channels(mesh) -> VertexChannels:
    """The vertex fields to export for ``mesh``."""

    text = mesh.get(LAYOUT_PROPERTY)

    if text:

        record = VertexLayoutRecord.from_json(str(text))
        channels = _recorded_channels(mesh, record) if record else None

        if channels is not None:

            return channels

    return _blender_made_channels(mesh)
