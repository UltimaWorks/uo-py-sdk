from __future__ import annotations

import struct
import sys
from array import array
from typing import Iterable

from ..errors import MulFormatError


def _u16_array_from_bytes(data: bytes) -> array:
    if len(data) % 2 != 0:
        raise MulFormatError("gump record length is not 16-bit aligned")
    a = array("H")
    a.frombytes(data)
    if sys.byteorder != "little":
        a.byteswap()
    return a


def _u32_array_from_bytes(data: bytes) -> array:
    if len(data) % 4 != 0:
        raise MulFormatError("gump record lookup table is not 32-bit aligned")
    a = array("I")
    a.frombytes(data)
    if sys.byteorder != "little":
        a.byteswap()
    return a


def decode_gump_to_1555(raw: bytes, *, width: int, height: int) -> list[int]:
    if width <= 0 or height <= 0:
        raise MulFormatError("gump has invalid dimensions")

    header_bytes = height * 4
    if len(raw) < header_bytes:
        raise MulFormatError("gump record truncated (lookup table)")

    lookups = _u32_array_from_bytes(raw[:header_bytes])
    src_u16 = _u16_array_from_bytes(raw)

    pixels = [0] * (width * height)

    for y in range(height):
        # lookup values are offsets in 4-byte units from the start of the record
        u16_pos = int(lookups[y]) * 2
        x = 0
        base = y * width

        while x < width:
            if u16_pos + 1 >= len(src_u16):
                raise MulFormatError("gump record truncated (rle)")
            color = int(src_u16[u16_pos])
            run = int(src_u16[u16_pos + 1])
            u16_pos += 2

            if run <= 0:
                raise MulFormatError("gump record has invalid run length")

            out_color = 0 if color == 0 else ((color ^ 0x8000) & 0xFFFF)

            end_x = x + run
            if end_x > width:
                raise MulFormatError("gump record row overruns width")

            if out_color != 0:
                pixels[base + x : base + end_x] = [out_color] * run
            x = end_x

    return pixels


def encode_gump_from_1555(width: int, height: int, pixels_1555: Iterable[int]) -> bytes:
    if width <= 0 or height <= 0:
        raise ValueError("width/height must be > 0")

    pixels = list(pixels_1555)
    if len(pixels) != width * height:
        raise ValueError("pixels length must be width*height")

    # First: height * 4 bytes lookup table (int32 offsets in 4-byte units)
    out = bytearray(height * 4)

    for y in range(height):
        row_start = y * width
        row = pixels[row_start : row_start + width]

        # Current row data offset (in 4-byte units from record start)
        offset = len(out) // 4
        struct.pack_into("<i", out, y * 4, int(offset))

        x = 0
        while x < width:
            c = int(row[x]) & 0xFFFF
            run = 1
            while x + run < width and (int(row[x + run]) & 0xFFFF) == c:
                run += 1

            stored = 0 if c == 0 else ((c ^ 0x8000) & 0xFFFF)
            out += struct.pack("<HH", stored, run & 0xFFFF)
            x += run

    return bytes(out)
