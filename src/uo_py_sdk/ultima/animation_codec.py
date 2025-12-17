from __future__ import annotations

import struct
from dataclasses import dataclass

from ..errors import MulFormatError


_DOUBLE_XOR = (0x200 << 22) | (0x200 << 12)
_SENTINEL = 0x7FFF7FFF


@dataclass(frozen=True, slots=True)
class AnimationFrame:
    width: int
    height: int
    center_x: int
    center_y: int
    pixels_1555: list[int]


def _u16_xor_8000(x: int) -> int:
    return (int(x) & 0xFFFF) ^ 0x8000


def decode_animation_record(data: bytes, *, flip: bool) -> list[AnimationFrame]:
    """Decode an Ultima-style animation record into frames.

    Record layout (UltimaSDK Animations.Frame):
    - palette: 256 * u16 (XOR 0x8000)
    - frame_count: i32
    - lookups: frame_count * i32 (offsets relative to start after palette)
    - frames...

    Each frame:
    - x_center: i16
    - y_center: i16
    - width: u16
    - height: u16
    - runs: repeated i32 header until 0x7FFF7FFF sentinel
      header is XORed with DoubleXor; packed coords + run length
      pixel bytes are palette indices
    """

    if len(data) < 512 + 4:
        raise MulFormatError("anim record truncated")

    off = 0

    # Palette (ARGB1555 values)
    palette: list[int] = []
    for _ in range(0x100):
        if off + 2 > len(data):
            raise MulFormatError("anim palette truncated")
        (raw,) = struct.unpack_from("<H", data, off)
        off += 2
        palette.append(_u16_xor_8000(raw))

    start = off
    if off + 4 > len(data):
        raise MulFormatError("anim missing frame_count")
    (frame_count,) = struct.unpack_from("<i", data, off)
    off += 4

    if frame_count < 0 or frame_count > 4096:
        raise MulFormatError(f"anim unreasonable frame_count={frame_count}")

    lookups: list[int] = []
    for _ in range(frame_count):
        if off + 4 > len(data):
            raise MulFormatError("anim lookup table truncated")
        (rel,) = struct.unpack_from("<i", data, off)
        off += 4
        lookups.append(start + int(rel))

    frames: list[AnimationFrame] = []
    for frame_off in lookups:
        if frame_off < 0 or frame_off >= len(data):
            # UltimaSDK tends to tolerate weird lookups; we treat as invalid.
            raise MulFormatError("anim frame lookup out of bounds")
        frame, _next = _decode_frame(data, frame_off, palette=palette, flip=flip)
        frames.append(frame)

    return frames


def _decode_frame(data: bytes, off: int, *, palette: list[int], flip: bool) -> tuple[AnimationFrame, int]:
    if off + 8 > len(data):
        raise MulFormatError("anim frame header truncated")

    x_center, y_center, width, height = struct.unpack_from("<hhHH", data, off)
    off += 8

    width_i = int(width)
    height_i = int(height)
    if width_i <= 0 or height_i <= 0:
        # UltimaSDK returns an empty Frame; we represent it as a 0x0 frame.
        return AnimationFrame(0, 0, int(x_center), int(y_center), []), off

    pixels: list[int] = [0] * (width_i * height_i)

    x_base = int(x_center) - 0x200
    y_base = (int(y_center) + height_i) - 0x200

    # Our delta is tightly packed row width.
    delta = width_i

    if not flip:
        base_x = x_base
    else:
        base_x = (width_i - 1) - x_base

    base_y = y_base

    while True:
        if off + 4 > len(data):
            raise MulFormatError("anim run header truncated")
        (header_raw,) = struct.unpack_from("<i", data, off)
        off += 4

        if header_raw == _SENTINEL:
            break

        header = int(header_raw) ^ _DOUBLE_XOR
        x_off = (header >> 22) & 0x3FF
        y_off = (header >> 12) & 0x3FF
        run = header & 0xFFF

        if run <= 0:
            continue

        dst_y = base_y + int(y_off)
        if not (0 <= dst_y < height_i):
            # Still need to consume the bytes.
            off += run
            continue

        if not flip:
            start_x = base_x + int(x_off)
            step = 1
        else:
            start_x = base_x - int(x_off)
            step = -1

        for i in range(run):
            if off >= len(data):
                raise MulFormatError("anim run pixels truncated")
            pal_idx = data[off]
            off += 1

            dst_x = start_x + (i * step)
            if 0 <= dst_x < width_i:
                pixels[dst_y * delta + dst_x] = int(palette[pal_idx]) & 0xFFFF

    if flip:
        x_center = width_i - int(x_center)

    return AnimationFrame(width_i, height_i, int(x_center), int(y_center), pixels), off
