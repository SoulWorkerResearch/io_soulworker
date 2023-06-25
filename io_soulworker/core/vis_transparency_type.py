
from enum import IntEnum


class VisTransparencyType(IntEnum):
    """ All available transparency type for surfaces/primitives """

    NONE = 0,
    """ no transparency """

    MULTIPLICATIVE = 1,
    """ multiplicative transparency """

    ALPHA = 2,
    """ regular alpha blending """

    ADDITIVE = 3,
    """ additive transparency """

    COLORKEY = 4,
    """ deprecated, renamed to ALPHATEST """

    ALPHATEST = 4,
    """ replaces 'COLORKEY' : no transparency, only alpha test """

    ADD_MODULATE = 5,
    """ add the modulated result (dest=dest*(1+src)) """

    ADDITIVE_NOALPHA = 6,
    """ additive transparency, ignoring source and destination alpha """

    NOCOLORWRITE = 7,
    """ no blend, no color write, no alpha test """

    MODULATE2X = 8,
    """ modulate and multiply by two """

    SUBTRACTIVE = 9,
    """ subtractive blending (dest-src*src.a) """

    PREMULTIPLIEDALPHA = 10,
    """ tractive blending (src+(dest*(1-src.a)) """

    ALPHA_NOALPHATEST_PARTICLES = 11,
    """ same as alpha without alphatest but selects special states for particles (internal use) """

    ALPHA_PARTICLES = 12,
    """ same as alpha but selects special states for particles (internal use) """

    ALPHA_NOALPHATEST = 15,
    """ same as alpha, but without alpha test (internal use) """
