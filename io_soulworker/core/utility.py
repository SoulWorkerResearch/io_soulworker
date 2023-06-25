def indices_to_face(indices: list[int], vertices_per_face=3):
    for offset in range(0, len(indices), vertices_per_face):
        yield indices[offset: offset + vertices_per_face]

# https://youtu.be/2N4tXf3Ensw
