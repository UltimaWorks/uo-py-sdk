from __future__ import annotations

from uo_py_sdk.ultima.gump_codec import decode_gump_to_1555, encode_gump_from_1555


def test_gump_encode_decode_roundtrip() -> None:
    width, height = 13, 9
    pixels: list[int] = []

    for y in range(height):
        for x in range(width):
            if (x * 3 + y) % 11 == 0:
                pixels.append(0)
            elif (x + y) % 2 == 0:
                pixels.append(0x8000 | (31 << 10))  # opaque red
            else:
                pixels.append(0x8000 | (0 << 10) | (31 << 5))  # opaque green

    raw = encode_gump_from_1555(width, height, pixels)
    decoded = decode_gump_to_1555(raw, width=width, height=height)
    assert decoded == pixels
