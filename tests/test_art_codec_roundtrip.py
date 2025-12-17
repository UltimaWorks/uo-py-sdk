from __future__ import annotations

from uo_py_sdk.ultima.art_codec import (
    decode_land_to_1555,
    decode_static_to_1555,
    encode_land_from_1555,
    encode_static_from_1555,
)


def test_land_encode_decode_roundtrip() -> None:
    # Build a simple 44x44 opaque gradient in ARGB1555 space.
    pixels = []
    for y in range(44):
        for x in range(44):
            r5 = (x * 31) // 43
            g5 = (y * 31) // 43
            b5 = 0
            pixels.append(0x8000 | (r5 << 10) | (g5 << 5) | b5)

    raw = encode_land_from_1555(pixels)
    decoded = decode_land_to_1555(raw)

    # Land records only encode the diamond; outside pixels are not represented.
    # Verify roundtrip only for pixels inside the diamond mask.
    def in_diamond(x: int, y: int) -> bool:
        if y < 22:
            start = 21 - y
            run = 2 + 2 * y
        else:
            yy = y - 22
            start = yy
            run = 44 - 2 * yy
        return start <= x < start + run

    for y in range(44):
        for x in range(44):
            if in_diamond(x, y):
                assert decoded[y * 44 + x] == pixels[y * 44 + x]


def test_static_encode_decode_roundtrip() -> None:
    width, height = 8, 6
    pixels = []
    for y in range(height):
        for x in range(width):
            if (x + y) % 3 == 0:
                pixels.append(0)  # transparent
            else:
                pixels.append(0x8000 | (31 << 10) | (0 << 5) | 0)  # opaque red

    raw = encode_static_from_1555(width, height, pixels)
    decoded = decode_static_to_1555(raw)
    assert decoded.width == width
    assert decoded.height == height
    assert decoded.pixels_1555 == pixels
