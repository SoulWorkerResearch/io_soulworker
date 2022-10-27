
from enum import IntEnum


class VisPrimitiveType(IntEnum):
    """ Enumeration that defines the primitive type used for rendering the buffer """

    TRILIST = 0,
    """ Renders vertices as a triangle list (up to vertexcount/3 primitives). """

    TRISTRIP = 1,
    """ Renders vertices as a triangle strip (up to vertexcount-2 primitives). """

    INDEXED_TRILIST = 2,
    """ Renders vertices as indexed triangle list. An index buffer has to be allocated for this mode. """

    INDEXED_TRISTRIP = 3,
    """ Renders vertices as indexed triangle strip. An index buffer has to be allocated for this mode. """

    LINELIST = 4,
    """ Renders vertices as lines (start/end pairs, up to vertexcount/2 lines). """

    INDEXED_LINELIST = 5,
    """ Renders vertices as indexed lines (index buffer contains start/end pairs). """

    POINTLIST = 6
    """ Renders vertices as point list. """
