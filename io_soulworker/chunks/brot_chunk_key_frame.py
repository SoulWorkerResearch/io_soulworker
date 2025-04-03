from io_soulworker.core.binary_reader import BinaryReader


from mathutils import Quaternion


class BrotChunk_KeyFrame:

    time: float
    quternin_list: list[Quaternion]

    def __init__(self, bone_count: int, reader: BinaryReader) -> None:

        self.time = reader.read_float()

        self.quternin_list = [
            reader.read_quaternion() for _ in range(bone_count)
        ]
