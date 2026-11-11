from __future__ import annotations

from typing import TYPE_CHECKING

from mathutils import Vector

from ..core.vis_transparency_type import VisTransparencyType

if TYPE_CHECKING:
    from ..core.materials_xml.shader_tag import ShaderTag


class VisMaterial:

    name: str
    """ name of this surface """

    diffuse: str
    """ the diffuse base texture of the material """

    shader: ShaderTag | None = None
    """ optional Shader tag from materials.xml """

    attributes: dict[str, str] | None = None
    """ raw ``<Material>`` attributes from materials.xml, kept for export """

    specularmap: str = ""
    """ ``specularmap`` attribute; overrides the MTRS specular map when set """

    normalmap: str = ""
    """ ``normalmap`` attribute; overrides the MTRS normal map when set """

    ambient: list[int]
    """ the ambient color of this surface """

    specmul: float | None = None
    """ specular multiplier (``materials.xml``); ``None`` if omitted """

    specexp: float | None = None
    """ specular exponent (``materials.xml``); ``None`` if omitted """

    parallaxscale: float | None = None
    """ parallax scale """

    parallaxbias: float | None = None
    """ parallax bias """

    lightmapsize: Vector  # x, y
    """ size of the lightmap """

    lightmap_id: int
    """ page-id of the used lightmap """

    userflags: int
    """ customizable user flags """

    sortingkey: int
    """ internal sorting key; has to be in the range 0..15 """

    doublesided: bool
    """ """

    lighting: str
    """ """

    render_pass: str
    """ """

    mobileflags: int
    """ """

    transparency: VisTransparencyType
    """ """

    alphathreshold: float
    """ custom alpha threshold; in case it is lower than 0, global alpha threshold is taken """

    depthwrite: bool
    """ """

    zbias: Vector  # x, y, z
    """ z-offset value that is passed to the shader """

    lightmapgran: int
    """ granularity of the lightmap """


# https://youtu.be/egpdUR24ETM
