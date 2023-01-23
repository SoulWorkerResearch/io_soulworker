
from enum import IntEnum


class VisRenderStateFlag(IntEnum):
    """ flags for simple render state flags """

    NONE = 00000000,
    """  """

    FRONTFACE = 00000001,
    """ The front faces are rendered (default). """

    BACKFACE = 00000002,
    """ The back faces are rendered. """

    DOUBLESIDED = FRONTFACE | BACKFACE,
    """  doublesided; combination of FRONTFACE and BACKFACE bit. """

    ALWAYSVISIBLE = 00000004,
    """ No z-test is performed while rendering. """

    WRITETOZBUFFER = 00000008,
    """ Rasterizer writes to z-buffer. """

    ALPHATEST = 00000010,
    """ Alpha test is performed using the global alpha threshold value. Only supported on platforms supporting the alpha test state (Windows DirectX9, Playstation 3, Xbox360). """

    USEFOG = 00000020,
    """  """

    LUMINANCETOALPHA = 00000040,
    """ Used for fonts that need to copy the luminance value into the alpha channel. """

    FILTERING = 00000080,
    """ Bilinear filtering is enabled on the used sampler(s) (otherwise just point sampling). """

    USEADDITIVEALPHA = 00000100,
    """ Determines whether additive blending multiplies the source color with source alpha. """

    SAMPLERCLAMPING = 00000200,
    """ If enabled, used sampler(s) use clamping """

    NOWIREFRAME = 00000400,
    """ Ignores the global wireframe mode (e.g. fonts should be displayed correctly also in wireframe mode). """

    USESCISSORTEST = 00000800,
    """ Enable scissor test. """

    NOMULTISAMPLING = 00001000,
    """  """

    CUSTOMBIT = 00008000,
    """ For custom usage (ignored by Vision). """
