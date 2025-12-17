from __future__ import annotations

import sys
from array import array
from dataclasses import dataclass
from typing import Iterable

from ..errors import MulFormatError
from ..images.color1555 import rgba_to_1555, u1555_to_rgba


@dataclass(frozen=True, slots=True)
class StaticArt:
    width: int
    height: int
    pixels_1555: list[int]  # row-major, length = width*height


def _u16_array_from_bytes(data: bytes) -> array:
    if len(data) % 2 != 0:
        raise MulFormatError("art record length is not 16-bit aligned")
    a = array("H")
    a.frombytes(data)
    if sys.byteorder != "little":
        a.byteswap()
    return a


def decode_land_to_1555(raw: bytes) -> list[int]:
    """Decode a land tile record to a 44x44 ARGB1555 pixel buffer.

    Matches UltimaSDK `LoadLand` logic.
    """

    src = _u16_array_from_bytes(raw)
    pixels = [0] * (44 * 44)

    i = 0
    x_offset = 21
    x_run = 2

    # Top 22 rows
    for y in range(22):
        row = y
        start_x = x_offset
        for x in range(start_x, start_x + x_run):
            if i >= len(src):
                raise MulFormatError("land record truncated")
            pixels[row * 44 + x] = int(src[i]) | 0x8000
            i += 1
        x_offset -= 1
        x_run += 2

    # Bottom 22 rows
    x_offset = 0
    x_run = 44
    for y in range(22):
        row = 22 + y
        start_x = x_offset
        for x in range(start_x, start_x + x_run):
            if i >= len(src):
                raise MulFormatError("land record truncated")
            pixels[row * 44 + x] = int(src[i]) | 0x8000
            i += 1
        x_offset += 1
        x_run -= 2

    return pixels


def encode_land_from_1555(pixels_1555: Iterable[int]) -> bytes:
    """Encode a 44x44 ARGB1555 pixel buffer into land record bytes.

    Matches UltimaSDK `LoadLand` byte order (diamond scan) and stores 15-bit colors.
    """

    pixels = list(pixels_1555)
    if len(pixels) != 44 * 44:
        raise ValueError("land pixels must be 44*44")

    out_u16: list[int] = []

    x_offset = 21
    x_run = 2
    for y in range(22):
        for x in range(x_offset, x_offset + x_run):
            out_u16.append(int(pixels[y * 44 + x]) & 0x7FFF)
        x_offset -= 1
        x_run += 2

    x_offset = 0
    x_run = 44
    for y in range(22):
        row = 22 + y
        for x in range(x_offset, x_offset + x_run):
            out_u16.append(int(pixels[row * 44 + x]) & 0x7FFF)
        x_offset += 1
        x_run -= 2

    arr = array("H", out_u16)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr.tobytes()


def decode_static_to_1555(raw: bytes) -> StaticArt:
    """Decode a static art record into a 1555 pixel buffer.

    Matches UltimaSDK `LoadStatic` logic.
    """

    src = _u16_array_from_bytes(raw)

    count = 2  # skip 4 bytes
    if len(src) < count + 2:
        raise MulFormatError("static record truncated")

    width = int(src[count])
    height = int(src[count + 1])
    count += 2

    if width <= 0 or height <= 0:
        raise MulFormatError("static record has invalid dimensions")

    start = height + 4
    if len(src) < start:
        raise MulFormatError("static record truncated (no lookup table)")

    lookups = [0] * height
    for y in range(height):
        if count >= len(src):
            raise MulFormatError("static record truncated (lookup table)")
        lookups[y] = start + int(src[count])
        count += 1

    pixels = [0] * (width * height)

    for y in range(height):
        pos = lookups[y]
        cur_x = 0
        while True:
            if pos + 1 >= len(src):
                raise MulFormatError("static record truncated (rle header)")
            x_offset = int(src[pos])
            x_run = int(src[pos + 1])
            pos += 2
            if x_offset + x_run == 0:
                break

            cur_x += x_offset
            if cur_x > width:
                break

            if cur_x + x_run > width:
                break

            for _ in range(x_run):
                if pos >= len(src):
                    raise MulFormatError("static record truncated (rle pixels)")
                pix = int(src[pos]) ^ 0x8000
                pos += 1
                pixels[y * width + cur_x] = pix
                cur_x += 1

    return StaticArt(width=width, height=height, pixels_1555=pixels)


def encode_static_from_1555(width: int, height: int, pixels_1555: list[int]) -> bytes:
    """Encode a static art record from ARGB1555 pixels using UltimaSDK's RLE format."""

    if width <= 0 or height <= 0:
        raise ValueError("width/height must be > 0")
    if len(pixels_1555) != width * height:
        raise ValueError("pixels length must be width*height")

    # Header: 2 ushorts padding, then width, height, then lookup table (height ushorts)
    header: list[int] = [0, 0, width & 0xFFFF, height & 0xFFFF]
    lookups: list[int] = [0] * height

    start = height + 4
    rle_data: list[int] = []

    # We build lookups as ushort offsets from `start`.
    pos = 0
    for y in range(height):
        lookups[y] = pos

        cursor = 0
        row = pixels_1555[y * width : (y + 1) * width]

        while cursor < width:
            # skip transparent
            while cursor < width and (row[cursor] & 0x8000) == 0:
                cursor += 1
            if cursor >= width:
                break

            run_start = cursor
            while cursor < width and (row[cursor] & 0x8000) != 0:
                cursor += 1
            run_end = cursor

            x_offset = run_start - (0 if not rle_data else 0)  # placeholder; computed below
            # x_offset is relative to *current* cursor position within the row RLE decoder.
            # The decoder maintains cur_x and adds x_offset each run.
            # We mirror this by tracking `cur_x` separately.
            #
            # Implemented by recomputing from a running cur_x.
            
        # Re-encode with correct x_offset tracking
        cur_x = 0
        cursor = 0
        while cursor < width:
            while cursor < width and (row[cursor] & 0x8000) == 0:
                cursor += 1
            if cursor >= width:
                break
            run_start = cursor
            while cursor < width and (row[cursor] & 0x8000) != 0:
                cursor += 1
            run_end = cursor

            x_offset = run_start - cur_x
            x_run = run_end - run_start
            rle_data.append(x_offset & 0xFFFF)
            rle_data.append(x_run & 0xFFFF)

            for x in range(run_start, run_end):
                # Stored pixels have alpha bit flipped, per UltimaSDK (xor 0x8000 on load).
                rle_data.append((int(row[x]) ^ 0x8000) & 0xFFFF)

            cur_x = run_end

        # terminator
        rle_data.extend([0, 0])

        pos = len(rle_data)

    out_u16 = header + [v & 0xFFFF for v in lookups] + [v & 0xFFFF for v in rle_data]
    arr = array("H", out_u16)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr.tobytes()


# Pillow helpers (optional)

def pixels1555_to_pil_rgba(width: int, height: int, pixels_1555: Iterable[int]):
    try:
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Pillow is required for image export. Install `uo-py-sdk[image]`.") from e

    pixels = list(pixels_1555)
    if len(pixels) != width * height:
        raise ValueError("pixel buffer size mismatch")

    img = Image.new("RGBA", (width, height))
    img.putdata([u1555_to_rgba(p) for p in pixels])
    return img


def pil_rgba_to_pixels1555(img) -> tuple[int, int, list[int]]:
    try:
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("Pillow is required for image import. Install `uo-py-sdk[image]`.") from e

    if not hasattr(img, "convert"):
        raise TypeError("img must be a PIL Image")

    rgba = img.convert("RGBA")
    width, height = rgba.size
    pixels = [rgba_to_1555(r, g, b, a) for (r, g, b, a) in rgba.getdata()]
    return width, height, pixels
