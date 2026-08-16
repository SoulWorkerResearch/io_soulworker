import enum


class VisChunkId(enum.IntEnum):

    NONE = int.from_bytes(b"NONE", byteorder="little")
    VBIN = int.from_bytes(b"VBIN", byteorder="little")

    # Mesh
    VMSH = int.from_bytes(b"VMSH", byteorder="big")

    # Legacy static mesh (skipped by Vision VBaseMesh loader)
    SMSH = int.from_bytes(b"SMSH", byteorder="big")

    # Vertex shadow-mesh relevance bitfield (1 bit/vertex → VDynamicMesh::SetShadowVertexRelevance)
    VSMR = int.from_bytes(b"VSMR", byteorder="big")

    # Triangle shadow-mesh relevance bitfield (1 bit/triangle → VDynamicMesh::SetShadowTriangleRelevance)
    TSMR = int.from_bytes(b"TSMR", byteorder="big")

    # Materials
    MTRS = int.from_bytes(b"MTRS", byteorder="big")

    # Material
    MTRL = int.from_bytes(b"MTRL", byteorder="big")

    # SubMeshes
    SUBM = int.from_bytes(b"SUBM", byteorder="big")

    # Export transform
    EXPR = int.from_bytes(b"EXPR", byteorder="big")

    # Skeleton
    SKEL = int.from_bytes(b"SKEL", byteorder="big")

    # Skeleton Weights
    WGHT = int.from_bytes(b"WGHT", byteorder="big")

    # Bounding box
    BBBX = int.from_bytes(b"BBBX", byteorder="big")

    # Custom Bone Property
    CBPR = int.from_bytes(b"CBPR", byteorder="big")

    BNDS = int.from_bytes(b"BNDS", byteorder="big")
    HEAD = int.from_bytes(b"HEAD", byteorder="big")

    # Scene (sky / sun params)
    ST5G = int.from_bytes(b"ST5G", byteorder="big")

    # Scene file chunks (.vscene)
    SCNE = int.from_bytes(b"SCNE", byteorder="big")
    EPLG = int.from_bytes(b"EPLG", byteorder="big")
    _V3D = int.from_bytes(b"_V3D", byteorder="big")
    _FOG = int.from_bytes(b"_FOG", byteorder="big")
    VIEW = int.from_bytes(b"VIEW", byteorder="big")
    ZONE = int.from_bytes(b"ZONE", byteorder="big")
    HVKP = int.from_bytes(b"HVKP", byteorder="big")
    SHPS = int.from_bytes(b"SHPS", byteorder="big")
    AINM = int.from_bytes(b"AINM", byteorder="big")

    # Animation
    ANIM = int.from_bytes(b"ANIM", byteorder="big")

    # Animation delta tracks
    ATDO = int.from_bytes(b"ATDO", byteorder="little")
    ATDR = int.from_bytes(b"ATDR", byteorder="little")
    ATDM = int.from_bytes(b"ATDM", byteorder="little")

    # Visibility Bounding Box
    VSBX = int.from_bytes(b"VSBX", byteorder="big")

    # Bone Animation
    BANI = int.from_bytes(b"BANI", byteorder="big")

    # Bone Position
    BPOS = int.from_bytes(b"BPOS", byteorder="big")

    # Bone Rotation
    BROT = int.from_bytes(b"BROT", byteorder="big")

    # Bone Scale
    BSCL = int.from_bytes(b"BSCL", byteorder="big")

    # Animation Events
    EVNT = int.from_bytes(b"EVNT", byteorder="big")

    # Vertex Animation
    VANI = int.from_bytes(b"VANI", byteorder="big")

    @staticmethod
    def get_name(id: int) -> str:

        try:
            return VisChunkId(id).name
        except ValueError:
            pass

        for order in ("big", "little"):
            try:
                return id.to_bytes(4, order).decode("ascii")
            except (OverflowError, UnicodeDecodeError, ValueError):
                continue

        return f"0x{id & 0xffffffff:08x}"

# https://yummyanime.tv/58-ljubovnye-neprijatnosti.html
