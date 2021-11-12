from logging import warn
from typing import Tuple
from xml.dom.minidom import Element
from xml.dom.minidom import Node
from xml.dom.minidom import parse
from pathlib import Path
from io_soulworker.core.vis_material import VisMaterial
from io import BufferedReader
from io import SEEK_CUR
from struct import unpack
from collections import abc


def indices_to_face(indices: abc, vertices_per_face: int = 3):
    return map(
        lambda id: indices[id: id + vertices_per_face],
        range(0, len(indices), vertices_per_face)
    )


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
