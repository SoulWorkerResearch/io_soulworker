from enum import IntFlag


class VisSurfaceFlags(IntFlag):
    """ Flags passed to the shader provider to control automatic shader assignment. """

    NONE = 0x00000000,
    """ No flags. """

    OBJECT_SPACE_COORDINATES = 0x00000001,
    """ Unused. """

    VERTEX_COLOR = 0x00000010,
    """ Select a shader that uses vertex colors. """

    NO_DEFAULT_SHADERS = 0x00001000,
    """ Don't fall back to default material shaders. """

    NO_DYNAMIC_LIGHT_SHADERS = 0x00002000,
    """ Don't select dynamic lighting shaders. """

    TRIGGER_CALLBACK_INTERNAL = 0x10000000,
    """ Used internally, do not use. """

    HAS_ADDITIONAL_FORWARD_PASS = 0x20000000,
    """ Select a shader that supports additional forward passes. """

    DEFAULT = NONE
