"""The exported vertices of a mesh, with corners that agree sharing one."""

from __future__ import annotations

from mathutils import Vector


NORMAL_MERGE_DISTANCE = 0.001
"""Corner normals closer than this are one normal on a mesh made in Blender.

Blender keeps a custom normal quantised, so the corners that were given one
normal differ by up to about 2e-4. Normals of a real crease differ by far
more.
"""

IMPORTED_NORMAL_MERGE_DISTANCE = 0.1
"""The same for a mesh that carries the layout it was imported with.

Every corner of such a vertex was given the normal of that vertex, so any
difference is storage error. Over 2.4 million vertices of 790 shipped meshes
the corners of a vertex differ by under 1e-4 in 99.9% of them, by up to 0.03
in the worst quantised case, and by 0.3 to 1 in 8 vertices where Blender could
not keep the normal. A crease made on purpose is wider than this.
"""


class VertexTable:
    """Hands out one exported vertex per distinct corner.

    Two corners share a vertex when their ``key`` (position, other fields,
    skin weights) is equal and their normals are within
    the table's normal tolerance. Each vertex remembers the lowest Blender
    vertex index among its corners; ``order`` lists the vertices by that
    index, so a mesh that was imported and not edited comes out in the order
    of the file.
    """

    def __init__(self, normal_tolerance: float = NORMAL_MERGE_DISTANCE) -> None:

        self._limit = normal_tolerance * normal_tolerance
        self._buckets: dict[tuple, list[int]] = {}
        self.positions: list[Vector] = []
        self.normals: list[Vector] = []
        self.values: list[tuple] = []
        self.sources: list[int] = []

    def __len__(self) -> int:

        return len(self.positions)

    def intern(
            self,
            key: tuple,
            position: Vector,
            normal: Vector,
            values: tuple,
            source: int) -> int:
        """The id of the vertex for this corner, made when it is new."""

        bucket = self._buckets.setdefault(key, [])

        for vertex in bucket:

            if (self.normals[vertex] - normal).length_squared <= self._limit:

                self.sources[vertex] = min(self.sources[vertex], source)
                return vertex

        vertex = len(self.positions)
        bucket.append(vertex)
        self.positions.append(position)
        self.normals.append(normal)
        self.values.append(values)
        self.sources.append(source)

        return vertex

    def order(self) -> list[int]:
        """Vertex ids by source vertex, then by when they were made."""

        return sorted(range(len(self.sources)),
                      key=lambda vertex: (self.sources[vertex], vertex))
