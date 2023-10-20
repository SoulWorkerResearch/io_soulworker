
import os
from pathlib import Path


class Defines:

    TEST_FILES: list[str] = []

    @staticmethod
    def __create_file_list__():
        path = Path(os.getcwd()) / "tests/datas/Models"

        files = ["MagicBall.model",
                 "MissingModel.model",
                 "Primitive_Box.model",
                 "Primitive_Cylinder.model",
                 "Primitive_Sphere.model",
                 "Sphere.model"]

        return [path / file for file in files]


Defines.TEST_FILES = Defines.__create_file_list__()
