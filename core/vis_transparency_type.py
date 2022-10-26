from enum import IntEnum


class VisTransparencyType(IntEnum):
    """ Enumeration type for the transparency setting of the Vision engine """

    NONE = 0,
    ALPHA = 2,
    ADDITIVE = 3,
    COLORKEY = 4,
    SUBTRACTIVE = 9
