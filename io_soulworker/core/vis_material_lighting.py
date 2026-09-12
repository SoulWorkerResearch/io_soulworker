from enum import Enum


class VisMaterialLighting(str, Enum):

    NONE = "None"
    LIGHTMAPPING = "Lightmapping"
    LIGHT_GRID = "LightGrid"
