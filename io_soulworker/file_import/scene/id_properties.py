from __future__ import annotations


def blender_id_int32(value: int) -> int:
    """Pack a uint32 bit mask into a Blender ID property (signed int32)."""

    value &= 0xFFFFFFFF

    return value - 0x100000000 if value >= 0x80000000 else value
