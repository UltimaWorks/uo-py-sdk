from __future__ import annotations

import sys
from array import array
from dataclasses import dataclass
from typing import Iterable

from ..errors import MulFormatError


@dataclass(frozen=True, slots=True)
class Texture:
    size: int  # 64 or 128
    pixels_1555: list[int]  # row-major, length=size*size


def _u16_array_from_bytes(data: bytes) -> array:
    if len(data) % 2 != 0:
        raise MulFormatError("texture record length is not 16-bit aligned")
    a = array("H")
    a.frombytes(data)
    if sys.byteorder != "little":
        a.byteswap()
    return a


def decode_texture_to_1555(raw: bytes, *, extra: int) -> Texture:
    size = 64 if extra == 0 else 128
    needed = size * size

    src = _u16_array_from_bytes(raw)
    if len(src) < needed:
        raise MulFormatError("texture record truncated")

    pixels = [(int(src[i]) ^ 0x8000) & 0xFFFF for i in range(needed)]
    return Texture(size=size, pixels_1555=pixels)


def encode_texture_from_1555(size: int, pixels_1555: Iterable[int]) -> tuple[bytes, int]:
    if size not in (64, 128):
        raise ValueError("texture size must be 64 or 128")

    pixels = list(pixels_1555)
    if len(pixels) != size * size:
        raise ValueError("pixels length must be size*size")

    extra = 0 if size == 64 else 1
    out_u16 = [((int(p) ^ 0x8000) & 0xFFFF) for p in pixels]

    arr = array("H", out_u16)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr.tobytes(), extra
