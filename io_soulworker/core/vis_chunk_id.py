import enum


class VisChunkId(enum.IntEnum):

    NONE = int.from_bytes(b"NONE", byteorder="little")
    VBIN = int.from_bytes(b"VBIN", byteorder="little")

    # Mesh
    VMSH = int.from_bytes(b"VMSH", byteorder="big")

    # Naterials
    MTRS = int.from_bytes(b"MTRS", byteorder="big")

    # Material
    MTRL = int.from_bytes(b"MTRL", byteorder="big")

    # Submaterial
    SUBM = int.from_bytes(b"SUBM", byteorder="big")
    EXPR = int.from_bytes(b"EXPR", byteorder="big")

    # Skelet
    SKEL = int.from_bytes(b"SKEL", byteorder="big")

    # Skelet Weights
    WGHT = int.from_bytes(b"WGHT", byteorder="big")

    # Bounding box
    BBBX = int.from_bytes(b"BBBX", byteorder="big")

    # Custom Bone Property
    CBPR = int.from_bytes(b"CBPR", byteorder="big")

    BNDS = int.from_bytes(b"BNDS", byteorder="big")
    HEAD = int.from_bytes(b"HEAD", byteorder="big")

    # Animation
    ANIM = int.from_bytes(b"ANIM", byteorder="big")

    # Animation Delata Offsets
    ATDO = int.from_bytes(b"ATDO", byteorder="big")

    # Animation Delta Rotation
    ATDR = int.from_bytes(b"ATDR", byteorder="big")

    # Visability Bounding Box
    VSBX = int.from_bytes(b"VSBX", byteorder="big")

    # Animation Delata Motion
    ATDM = int.from_bytes(b"ATDM", byteorder="big")

    # Bone Animation
    BANI = int.from_bytes(b"BANI", byteorder="big")

    # Bone Position
    BPOS = int.from_bytes(b"BPOS", byteorder="big")

    # Bone Rotation
    BROT = int.from_bytes(b"BROT", byteorder="big")

# https://yummyanime.tv/58-ljubovnye-neprijatnosti.html
