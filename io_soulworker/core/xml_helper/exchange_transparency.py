from logging import warn

from io_soulworker.core.vis_transparency_type import VisTransparencyType


def exchange_transparency(name: str) -> VisTransparencyType:

    match name.lower():

        case "opaque":
            return VisTransparencyType.NONE

        case "modulate":
            return VisTransparencyType.MULTIPLICATIVE

        case "alpha":
            return VisTransparencyType.ALPHA

        case "additive":
            return VisTransparencyType.ADDITIVE

        case "colorkey" | "alphatest":
            return VisTransparencyType.COLORKEY

        case "addmodulate":
            return VisTransparencyType.ADD_MODULATE

        case "additivenoalpha":
            return VisTransparencyType.ADDITIVE_NOALPHA

        case "nocolorwrite":
            return VisTransparencyType.NOCOLORWRITE

        case "modulate2x":
            return VisTransparencyType.MODULATE2X

        case "subtractive":
            return VisTransparencyType.SUBTRACTIVE

        case "alphasmooth":
            return VisTransparencyType.ALPHA_NOALPHATEST

        case "premultipliedalpha":
            return VisTransparencyType.PREMULTIPLIEDALPHA

        case _:
            warn('Undefined transparency type')
            return VisTransparencyType.NONE
