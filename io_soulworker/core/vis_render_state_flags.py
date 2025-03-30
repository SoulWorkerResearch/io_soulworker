
from enum import IntFlag


class VisRenderStateFlag(IntFlag):
    """ Flags for simple render state flags """

    NONE = 0x00000000,
    """  """

    FRONTFACE = 0x00000001,
    """ The front faces are rendered (default). """

    BACKFACE = 0x00000002,
    """ The back faces are rendered. """

    DOUBLESIDED = (0x00000001 | 0x00000002),
    """  doublesided; combination of FRONTFACE and BACKFACE bit. """

    ALWAYSVISIBLE = 0x00000004,
    """ No z-test is performed while rendering. """

    WRITETOZBUFFER = 0x00000008,
    """ Rasterizer writes to z-buffer. """

    ALPHATEST = 0x00000010,
    """ Alpha test is performed using the global alpha threshold value. Only supported on platforms supporting the alpha test state (Windows DirectX9, Playstation 3, Xbox360). """

    USEFOG = 0x00000020,
    """  """

    LUMINANCETOALPHA = 0x00000040,
    """ Used for fonts that need to copy the luminance value into the alpha channel. """

    FILTERING = 0x00000080,
    """ Bilinear filtering is enabled on the used sampler(s) (otherwise just point sampling). """

    USEADDITIVEALPHA = 0x00000100,
    """ Determines whether additive blending multiplies the source color with source alpha. """

    SAMPLERCLAMPING = 0x00000200,
    """ If enabled, used sampler(s) use clamping """

    NOWIREFRAME = 0x00000400,
    """ Ignores the global wireframe mode (e.g. fonts should be displayed correctly also in wireframe mode). """

    USESCISSORTEST = 0x00000800,
    """ Enable scissor test. """

    NOMULTISAMPLING = 0x00001000,
    """  """

    CUSTOMBIT = 0x00008000,
    """ For custom usage (ignored by Vision). """
