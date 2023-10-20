
from glob import glob
from logging import debug
from pathlib import Path


class Defines:

    TEST_FILES = list(Path("tests/datas/Models").glob("*.model"))
