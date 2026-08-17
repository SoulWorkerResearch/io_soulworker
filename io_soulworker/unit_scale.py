from mathutils import Matrix, Quaternion, Vector


_FACTOR = 100


def vision_to_blender(value: float | Vector | Quaternion) -> float | Vector | Quaternion:
    return value * (1 / _FACTOR)


def blender_to_vision(value: float | Vector | Quaternion) -> float | Vector | Quaternion:
    return value * _FACTOR


def vision_matrix_to_blender(matrix: Matrix) -> Matrix:
    """Convert a Vision world matrix to Blender space.

    Mesh vertices are already scaled by ``vision_to_blender`` on import, so only
    the translation is divided by the unit factor; rotation/scale stay as-is.
    """

    result = matrix.copy()
    result.translation = vision_to_blender(result.translation)
    return result
