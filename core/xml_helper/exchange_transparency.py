from io_soulworker.core.vis_transparency_type import VisTransparencyType

def exchange_transparency(name: str) -> VisTransparencyType:
  if name == "opaque":
    return VisTransparencyType.NONE
  if name == "modulate":
    return VisTransparencyType.MULTIPLICATIVE
  if name == "alpha":
    return VisTransparencyType.ALPHA
  if name == "additive":
    return VisTransparencyType.ADDITIVE
  if name == "colorkey" or name == "alphatest":
    return VisTransparencyType.COLORKEY
  if name == "addmodulate":
    return VisTransparencyType.ADD_MODULATE
  if name == "additivenoalpha":
    return VisTransparencyType.ADDITIVE_NOALPHA
  if name == "nocolorwrite":
    return VisTransparencyType.NOCOLORWRITE
  if name == "modulate2x":
    return VisTransparencyType.MODULATE2X
  if name == "subtractive":
    return VisTransparencyType.SUBTRACTIVE
  if name == "alphasmooth":
    return VisTransparencyType.ALPHA_NOALPHATEST
  if name == "premultipliedalpha":
    return VisTransparencyType.PREMULTIPLIEDALPHA

  assert 0