from enum import Enum


# Flags passed to the shader provider to control automatic shader assignment.
class VisSurfaceFlags(Enum):
    # No flags.
    NONE = 0x00000000,

    # Unused.
    ObjectSpaceCoordinates = 0x00000001,

    # Select a shader that uses vertex colors.
    VertexColor = 0x00000010,

    # Don't fall back to default material shaders.
    NoDefaultShaders = 0x00001000,

    # Don't select dynamic lighting shaders.
    NoDynamicLightShaders = 0x00002000,

    # Used internally, do not use.
    TriggerCallback_Internal = 0x10000000,

    # Select a shader that supports additional forward passes.
    HasAdditionalForwardPass = 0x20000000,

    DEFAULT = NONE
