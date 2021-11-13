from logging import warn
from xml.dom.minidom import Element
from xml.dom.minidom import Node
from xml.dom.minidom import parse
from pathlib import Path
from io import BufferedReader
from io import SEEK_CUR
from struct import unpack
from collections import abc

from io_soulworker.core.vis_color import VisColor
from io_soulworker.core.vis_material import VisMaterial
from io_soulworker.core.vis_material_effect import VisMaterialEffect


def read_mesh_config_effects(reader: BufferedReader) -> list[VisMaterialEffect]:
    count, = unpack("<I", reader.read(4))

    def read():
        library = read_string(reader)
        name = read_string(reader)
        param = read_string(reader)

        return VisMaterialEffect(library, name, param)

    return [read() for _ in range(count)]


def read_color(reader: BufferedReader) -> VisColor:
    r, g, b, a, = unpack(f"<{4}B", reader.read(4))

    return VisColor(r, g, b, a)


def read_string(reader: BufferedReader) -> str:
    length, = unpack("<I", reader.read(4))
    value, = unpack("<%ss" % length, reader.read(length))

    return value.decode('ASCII')


def indices_to_face(indices: abc, vertices_per_face: int = 3):
    iterator = range(0, len(indices), vertices_per_face)
    return map(lambda id: indices[id: id + vertices_per_face], iterator)


def skip_string(file: BufferedReader):
    length = unpack("<I", file.read(4))[0]
    file.seek(length, SEEK_CUR)


def parse_materials(path: Path) -> dict[str, VisMaterial]:
    if not path.exists():
        warn("no materials.xml present")
        return dict()

    xml: Element = parse(path.as_posix())
    xml.normalize()

    root: Element = xml.getElementsByTagName("root")[0]
    materials: Element = root.getElementsByTagName("Materials")[0]

    def process(node: Element) -> list[str, VisMaterial]:
        material = VisMaterial()
        material.name = node.getAttribute("name")

        material.ambient = [int(v)
                            for v in node.getAttribute("ambient").split(',')]

        material.diffuse = node.getAttribute("diffuse")
        material.transparency = node.getAttribute("transparency")
        material.alphathreshold = float(node.getAttribute("alphathreshold"))

        return [material.name, material]

    return dict(map(process, (node for node in materials.childNodes if node.nodeType == Node.ELEMENT_NODE)))


# https://youtu.be/2N4tXf3Ensw
