from enum import IntFlag


class VisLightingMethod(IntFlag):
    """ Enumeration for supported static lighting methods used for materials """

    FULLBRIGHT = 0,
    LIGHTMAPPING = 1,
    LIGHTGRID = 2,
    DYNAMIC_ONLY = 3
