import enum


class VChunkId(enum.IntEnum):
    VMSH = int.from_bytes(b"VMSH", byteorder="big")
    MTRS = int.from_bytes(b"MTRS", byteorder="big")
    SUBM = int.from_bytes(b"SUBM", byteorder="big")
    EXPR = int.from_bytes(b"EXPR", byteorder="big")
    SKEL = int.from_bytes(b"SKEL", byteorder="big")
    WGHT = int.from_bytes(b"WGHT", byteorder="big")
    BBBX = int.from_bytes(b"BBBX", byteorder="big")
    CBPR = int.from_bytes(b"CBPR", byteorder="big")
    BNDS = int.from_bytes(b"BNDS", byteorder="big")
    HEAD = int.from_bytes(b"HEAD", byteorder="big")
