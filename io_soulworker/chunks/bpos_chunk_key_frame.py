from io_soulworker.core.binary_reader import BinaryReader


from mathutils import Vector


class BposChunk_KeyFrame:

    time: float
    vector_list: list[Vector]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.time = reader.read_float()

        self.vector_list = [
            reader.read_float_vector3() for _ in range(bone_count)
        ]

        for i in range(bone_count):

            self.vector_list[i].w = 1.0
