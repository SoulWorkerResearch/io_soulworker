from enum import Enum


# All available transparency type for surfaces/primitives
class VisTransparencyType(Enum):
    # no transparency
    NONE = 0,

    # multiplicative transparency
    MULTIPLICATIVE = 1,

    # regular alpha blending
    ALPHA = 2,

    # additive transparency
    ADDITIVE = 3,

    # deprecated, renamed to ALPHATEST
    COLORKEY = 4,

    # replaces 'COLORKEY' : no transparency, only alpha test
    ALPHATEST = 4,

    # add the modulated result (dest=dest*(1+src))
    ADD_MODULATE = 5,

    # additive transparency, ignoring source and destination alpha
    ADDITIVE_NOALPHA = 6,

    # no blend, no color write, no alpha test
    NOCOLORWRITE = 7,

    # modulate and multiply by two
    MODULATE2X = 8,

    # subtractive blending (dest-src*src.a)
    SUBTRACTIVE = 9,

    # tractive blending (src+(dest*(1-src.a))
    PREMULTIPLIEDALPHA = 10,

    # e as alpha without alphatest but selects special states for particles (internal use)
    ALPHA_NOALPHATEST_PARTICLES = 11,

    # same as alpha but selects special states for particles (internal use)
    ALPHA_PARTICLES = 12,

    # e as alpha, but without alpha test (internal use)
    ALPHA_NOALPHATEST = 15,
