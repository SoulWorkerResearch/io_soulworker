from io_soulworker.core.vis_transparency_type import VisTransparencyType
from io_soulworker.core.vis_vector_3_int import VisVector3Int
from io_soulworker.core.vis_vector_2_int import VisVector2Int


class VisMaterial:
    name: str
    """ name of this surface """

    diffuse: str
    """ the diffuse base texture of the material """

    ambient: list[int]
    """ the ambient color of this surface """

    specmul: int
    """ specular multiplier """

    specexp: int
    """ specular exponent """

    parallaxscale: float
    """ parallax scale """

    parallaxbias: float
    """ parallax bias """

    lightmapsize: VisVector2Int
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

    zbias: VisVector3Int
    """ z-offset value that is passed to the shader """

    lightmapgran: int
    """ granularity of the lightmap """


# https://youtu.be/egpdUR24ETM
