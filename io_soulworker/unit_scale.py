from mathutils import Quaternion, Vector


_FACTOR = 100


def vision_to_blender(value: float | Vector | Quaternion) -> float | Vector | Quaternion:
    return value * (1 / _FACTOR)


def blender_to_vision(value: float | Vector | Quaternion) -> float | Vector | Quaternion:
    return value * _FACTOR
