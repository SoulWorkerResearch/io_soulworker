from typing import Tuple
from xml.dom.minidom import Element, Node, parse
from pathlib import Path
from io_soulworker.core.v_material import VMaterial
from io import BufferedReader, SEEK_CUR
from struct import unpack
from collections import abc


def indices_to_face(values: abc, vertices_in_face: int = 3):
    return map(
        lambda id: values[id: id + vertices_in_face],
        range(0, len(values), vertices_in_face)
    )


def skip_string(file: BufferedReader):
    length = unpack("<I", file.read(4))[0]
    file.seek(length, SEEK_CUR)


def parse_materials(path: Path) -> dict[str, VMaterial]:
    if not path.exists():
        return dict()

    xml: Element = parse(path.as_posix())
    xml.normalize()

    root: Element = xml.getElementsByTagName("root")[0]
    materials: Element = root.getElementsByTagName("Materials")[0]

    def process(node: Element) -> Tuple[str, VMaterial]:
        m = VMaterial()
        m.name = node.getAttribute("name")
        m.diffuse = node.getAttribute("diffuse")

        return [m.name, m]

    return dict(map(process, (node for node in materials.childNodes if node.nodeType == Node.ELEMENT_NODE)))

# https://youtu.be/2N4tXf3Ensw
