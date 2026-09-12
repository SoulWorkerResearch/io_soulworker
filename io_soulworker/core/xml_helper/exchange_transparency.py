from logging import warning

from io_soulworker.core.vis_transparency_type import VisTransparencyType


_TRANSPARENCY_TO_NAME = {
    VisTransparencyType.NONE: "opaque",
    VisTransparencyType.MULTIPLICATIVE: "modulate",
    VisTransparencyType.ALPHA: "alpha",
    VisTransparencyType.ADDITIVE: "additive",
    VisTransparencyType.ALPHATEST: "alphatest",
    VisTransparencyType.ADD_MODULATE: "addmodulate",
    VisTransparencyType.ADDITIVE_NOALPHA: "additivenoalpha",
    VisTransparencyType.NOCOLORWRITE: "nocolorwrite",
    VisTransparencyType.MODULATE2X: "modulate2x",
    VisTransparencyType.SUBTRACTIVE: "subtractive",
    VisTransparencyType.PREMULTIPLIEDALPHA: "premultipliedalpha",
    VisTransparencyType.ALPHA_NOALPHATEST: "alphasmooth",
}


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
            warning('Undefined transparency type')
            return VisTransparencyType.NONE


def transparency_to_exchange(value: VisTransparencyType) -> str:
    """Inverse of ``exchange_transparency`` for materials.xml attributes."""

    return _TRANSPARENCY_TO_NAME.get(value, "opaque")
