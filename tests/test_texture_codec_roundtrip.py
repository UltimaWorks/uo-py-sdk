from __future__ import annotations

from uo_py_sdk.ultima.textures_codec import decode_texture_to_1555, encode_texture_from_1555


def test_texture_encode_decode_roundtrip_64() -> None:
    size = 64
    pixels = []
    for y in range(size):
        for x in range(size):
            if (x + y) % 7 == 0:
                pixels.append(0)
            else:
                r5 = (x * 31) // (size - 1)
                g5 = (y * 31) // (size - 1)
                b5 = 0
                pixels.append(0x8000 | (r5 << 10) | (g5 << 5) | b5)

    raw, extra = encode_texture_from_1555(size, pixels)
    decoded = decode_texture_to_1555(raw, extra=extra)

    assert decoded.size == size
    assert decoded.pixels_1555 == pixels


def test_texture_encode_decode_roundtrip_128() -> None:
    size = 128
    pixels = [0x8000 | (31 << 10) for _ in range(size * size)]

    raw, extra = encode_texture_from_1555(size, pixels)
    decoded = decode_texture_to_1555(raw, extra=extra)

    assert decoded.size == size
    assert decoded.pixels_1555 == pixels
