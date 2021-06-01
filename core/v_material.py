from io_soulworker.core.v_vector_3_int import VVector3Int
from io_soulworker.core.v_material_transparency import VMaterialTransparency
from io_soulworker.core.v_color import VColor
from io_soulworker.core.v_vector_2_int import VVector2Int


class VMaterial:
    name: str
    diffuse: str
    ambient: VColor
    specmul: int
    specexp: int
    parallaxscale: float
    parallaxbias: float
    lightmapsize: VVector2Int
    lightmap_id: int
    userflags: int
    sortingkey: int
    doublesided: bool
    lighting: str
    render_pass: str
    mobileflags: int
    transparency: VMaterialTransparency
    alphathreshold: float
    depthwrite: bool
    zbias: VVector3Int
    lightmapgran: int
