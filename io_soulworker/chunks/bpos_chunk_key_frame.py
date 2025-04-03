from io_soulworker.core.binary_reader import BinaryReader


from mathutils import Vector


class BposChunk_KeyFrame:

    time: float
    vector_list: list[Vector]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.time = reader.read_float()

        self.vector_list = [
            Vector([*(reader.read_float() for _ in range(3)), 1.0]) for _ in range(bone_count)
        ]
