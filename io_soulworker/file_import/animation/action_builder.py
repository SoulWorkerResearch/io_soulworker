from collections.abc import Iterable, Sequence
from typing import Any


VISION_FRAMES_PER_SECOND = 33


def vision_time_to_frame(time: float) -> int:
    return round(time * VISION_FRAMES_PER_SECOND) + 1


def group_keyframes_by_bone(
    keyframes: Iterable[Any],
    bone_names: Sequence[str],
    values_attr: str,
) -> dict[str, list[tuple[int, Any]]]:
    grouped = {name: [] for name in bone_names}

    for keyframe in keyframes:
        frame = vision_time_to_frame(keyframe.time)
        values = getattr(keyframe, values_attr)

        for bone_index, bone_name in enumerate(bone_names):
            if bone_index >= len(values):
                break

            grouped[bone_name].append((frame, values[bone_index]))

    return grouped
