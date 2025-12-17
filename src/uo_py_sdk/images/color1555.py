from __future__ import annotations


def u1555_to_rgba(pixel: int) -> tuple[int, int, int, int]:
    """Convert 16-bit ARGB1555 (as used by UltimaSDK) to RGBA8888."""

    pixel = int(pixel) & 0xFFFF
    a = 255 if (pixel & 0x8000) else 0
    r5 = (pixel >> 10) & 0x1F
    g5 = (pixel >> 5) & 0x1F
    b5 = pixel & 0x1F
    r = (r5 * 255) // 31
    g = (g5 * 255) // 31
    b = (b5 * 255) // 31
    return r, g, b, a


def rgba_to_1555(r: int, g: int, b: int, a: int) -> int:
    """Convert RGBA8888 to ARGB1555.

    Any `a > 0` becomes opaque (alpha bit set).
    """

    r5 = (int(r) * 31 + 127) // 255
    g5 = (int(g) * 31 + 127) // 255
    b5 = (int(b) * 31 + 127) // 255
    alpha = 0x8000 if int(a) > 0 else 0
    return alpha | (r5 << 10) | (g5 << 5) | b5
