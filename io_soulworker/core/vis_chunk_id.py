import enum


class VisChunkId(enum.IntEnum):

    NONE = int.from_bytes(b"NONE", byteorder="little")
    VBIN = int.from_bytes(b"VBIN", byteorder="little")

    # Mesh
    VMSH = int.from_bytes(b"VMSH", byteorder="big")

    MTRS = int.from_bytes(b"MTRS", byteorder="big")
    MTRL = int.from_bytes(b"MTRL", byteorder="big")
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
