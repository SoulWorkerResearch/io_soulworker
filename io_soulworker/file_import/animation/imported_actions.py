"""Which actions an ``.anim`` import made, and for which armature.

An imported action is baked against one armature: its curves hold pose-bone
transforms computed from that armature's rest pose. Two armatures built from
the same skeleton can therefore play the same action, and armatures with other
skeletons cannot.

Custom properties keep track of this:

* every action carries the ``.anim`` path it came from, the sequence name, the
  position of the sequence in the file and a key of the skeleton it was baked
  against;
* every armature lists, per ``.anim`` path, the actions it plays.
"""

from __future__ import annotations

from hashlib import sha1
from json import dumps, loads

import bpy
from bpy.types import Action, Object


ACTION_SOURCE_PROPERTY = "soulworker_source_file"
"""Custom property that marks an action as imported from this ``.anim`` path."""

ACTION_SEQUENCE_PROPERTY = "soulworker_sequence"
"""Sequence name inside the ``.anim`` that an action was baked from."""

ACTION_SEQUENCE_INDEX_PROPERTY = "soulworker_sequence_index"
"""Position of the sequence in the ``.anim`` (the last one stays assigned)."""

ACTION_SKELETON_PROPERTY = "soulworker_skeleton_key"
"""Key of the skeleton an action was baked against (see ``skeleton_key``)."""

ARMATURE_ACTIONS_PROPERTY = "soulworker_imported_actions"
"""JSON ``{anim path: [action names]}`` of the actions an armature plays."""


def skeleton_key(armature_object: Object) -> str:
    """Identify an armature's skeleton: bone names, hierarchy and rest data.

    Armatures built from the same skeleton chunk share the stored
    ``soulworker_skeleton`` text, so its hash is enough. Other armatures are
    keyed by their bones' names, parents and rest matrices.
    """

    serialized = armature_object.get("soulworker_skeleton")

    if serialized:
        return sha1(str(serialized).encode("utf-8")).hexdigest()

    lines = []

    for bone in armature_object.data.bones:
        parent = bone.parent.name if bone.parent is not None else ""
        rest = ",".join(
            format(value, ".5f")
            for row in bone.matrix_local
            for value in row
        )
        lines.append("|".join((bone.name, parent, rest)))

    return sha1("\n".join(lines).encode("utf-8")).hexdigest()


def _listed_names(armature_object: Object) -> dict[str, list[str]]:

    try:
        listed = loads(armature_object.get(ARMATURE_ACTIONS_PROPERTY, "{}"))
    except (TypeError, ValueError):
        return {}

    return listed if isinstance(listed, dict) else {}


def imported_actions(armature_object: Object, source: str) -> list[Action]:
    """Actions of ``source`` that this armature plays, in sequence order."""

    actions = []

    for name in _listed_names(armature_object).get(source, []):
        action = bpy.data.actions.get(name)

        if action is not None and action.get(ACTION_SOURCE_PROPERTY) == source:
            actions.append(action)

    return actions


def remember_actions(
        armature_object: Object,
        source: str,
        actions: list[Action]) -> None:
    """Make ``actions`` the ones this armature plays from ``source``."""

    listed = _listed_names(armature_object)
    listed[source] = [action.name for action in actions]
    armature_object[ARMATURE_ACTIONS_PROPERTY] = dumps(listed)


def forget_action(
        armature_object: Object,
        source: str,
        action: Action) -> None:

    remember_actions(
        armature_object,
        source,
        [
            other for other in imported_actions(armature_object, source)
            if other != action
        ],
    )


def is_played_by_other_armature(
        action: Action,
        armature_object: Object) -> bool:
    """Whether any armature besides ``armature_object`` lists ``action``."""

    source = action.get(ACTION_SOURCE_PROPERTY)

    for other in bpy.data.objects:
        if (
            other.type == "ARMATURE"
            and other != armature_object
            and action.name in _listed_names(other).get(source, [])
        ):
            return True

    return False


def reusable_actions(source: str, key: str) -> list[Action]:
    """Actions imported from ``source`` and baked against skeleton ``key``."""

    found = [
        action for action in bpy.data.actions
        if action.get(ACTION_SOURCE_PROPERTY) == source
        and action.get(ACTION_SKELETON_PROPERTY) == key
    ]

    return sorted(
        found,
        key=lambda action: action.get(ACTION_SEQUENCE_INDEX_PROPERTY, 0),
    )


def assign_action(armature_object: Object, action: Action) -> None:
    """Play ``action`` on ``armature_object``, picking a slot when it has one.

    A new action has no slot yet: Blender makes one when the first curve is
    added. A shared action already has the slot of the armature it was baked
    for, and an armature with another name is not given that slot by itself.
    """

    animation_data = armature_object.animation_data_create()
    animation_data.action = action
    suitable = getattr(animation_data, "action_suitable_slots", None)

    if suitable and animation_data.action_slot is None:
        animation_data.action_slot = suitable[0]
