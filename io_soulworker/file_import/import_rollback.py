from __future__ import annotations

from collections.abc import Iterable
from logging import debug, error

import bpy
from bpy.types import Context, ID


_REMOVAL_ORDER = (
    "objects",
    "collections",
    "meshes",
    "armatures",
    "materials",
    "images",
)
"""Datablock collections of ``bpy.data``, users before the data they use."""

_COLLECTION_OF_ID_TYPE = {
    "OBJECT": "objects",
    "COLLECTION": "collections",
    "MESH": "meshes",
    "ARMATURE": "armatures",
    "MATERIAL": "materials",
    "IMAGE": "images",
}


def _is_alive(item: ID) -> bool:

    try:

        item.name

    except ReferenceError:

        return False

    return True


class DataSnapshot:
    """Remembers which datablocks exist, so that a failed import can remove
    exactly the ones it added and leave everything else alone.

    A datablock is recognised by its address in memory, which does not change
    while the datablock lives; a name could be taken by a newer datablock.
    Capturing reads only the datablocks of the given kinds, so a caller that
    knows what it will create can name those kinds and nothing more.
    """

    MODEL_DATA = ("objects", "meshes", "armatures", "materials", "images")
    """What importing a model creates."""

    def __init__(
            self,
            context: Context,
            categories: Iterable[str] = MODEL_DATA) -> None:

        view_layer = context.view_layer

        self.context = context
        self._known = {
            name: {item.as_pointer() for item in getattr(bpy.data, name)}
            for name in categories
        }
        self._active_object = view_layer.objects.active
        self._active_layer_collection = view_layer.active_layer_collection

    def created(self) -> list[ID]:
        """Datablocks of the captured kinds that were not there at capture."""

        return [
            item
            for name, known in self._known.items()
            for item in getattr(bpy.data, name)
            if item.as_pointer() not in known
        ]

    def discard(self, items: Iterable[ID]) -> int:
        """Remove ``items``, then give back the active object and collection.

        Returns how many datablocks were removed. An image that something else
        still uses stays.
        """

        doomed = {
            item.as_pointer(): item for item in items if _is_alive(item)
        }

        self._leave_edit_mode(doomed)

        # Sort first: a removed datablock cannot be asked what it was.
        by_collection: dict[str, list[ID]] = {
            name: [] for name in _REMOVAL_ORDER
        }

        for item in doomed.values():

            name = _COLLECTION_OF_ID_TYPE.get(item.id_type)

            if name is None:

                debug("keep %s: not a kind this import creates", item.name)
                continue

            by_collection[name].append(item)

        removed = 0

        for name in _REMOVAL_ORDER:

            collection = getattr(bpy.data, name)

            for item in by_collection[name]:

                if name == "images" and item.users:

                    debug("keep image %s: %d user(s)", item.name, item.users)
                    continue

                collection.remove(item)
                removed += 1

        self._restore_active()

        return removed

    def _leave_edit_mode(self, doomed: dict[int, ID]) -> None:
        """A failure can leave the new armature in edit mode; leave the mode
        before the armature is removed."""

        active = self.context.view_layer.objects.active

        if (
            active is None
            or active.as_pointer() not in doomed
            or active.mode == "OBJECT"
        ):
            return

        try:

            bpy.ops.object.mode_set(mode="OBJECT")

        except RuntimeError as exc:

            error("cannot leave %s mode: %s", active.mode, exc)

    def _restore_active(self) -> None:

        view_layer = self.context.view_layer
        previous = self._active_object

        if (
            previous is not None
            and _is_alive(previous)
            and previous.name in view_layer.objects
        ):
            view_layer.objects.active = previous

        layer_collection = self._active_layer_collection

        try:

            if view_layer.active_layer_collection != layer_collection:

                view_layer.active_layer_collection = layer_collection

        except (ReferenceError, RuntimeError):

            debug("the active collection no longer exists")
