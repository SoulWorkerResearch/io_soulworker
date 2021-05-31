from collections import abc


def indices_to_face(values: abc, vertices_in_face: int = 3):
    return map(
        lambda id: values[id: id + vertices_in_face],
        range(0, len(values), vertices_in_face)
    )
