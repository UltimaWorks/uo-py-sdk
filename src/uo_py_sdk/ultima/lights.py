from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import MulFormatError
from .file_index import FileIndex



def _dims_from_extra(length: int, extra: int) -> tuple[int, int] | None:
    # UltimaSDK's Light.cs historically treats extra as packed dimensions,
    # but there is ambiguity in bit order across tools.
    # We accept either ordering and prefer the one whose product matches `length`.
    a = int(extra) & 0xFFFF
    b = (int(extra) >> 16) & 0xFFFF

    w1, h1 = a, b
    w2, h2 = b, a

    def ok(w: int, h: int) -> bool:
        return w > 0 and h > 0 and (w * h) == int(length) and (w * h) <= 64_000_000

    if ok(w2, h2):
        return w2, h2
    if ok(w1, h1):
        return w1, h1

    # If nothing matches, still provide a sane-ish pair if small.
    if (w2 > 0 and h2 > 0) and (w2 * h2) <= 64_000_000:
        return w2, h2
    if (w1 > 0 and h1 > 0) and (w1 * h1) <= 64_000_000:
        return w1, h1

    return None


def decode_light_to_1555(raw: bytes) -> list[int]:
    """Decode light.mul payload bytes to ARGB1555 grayscale pixels.

    Each byte is an s8 delta applied to 0x1F for RGB channels.
    """

    out: list[int] = []
    for b in raw:
        # Interpret as signed byte.
        v = b - 256 if b >= 128 else b
        c5 = 0x1F + int(v)
        if c5 < 0:
            c5 = 0
        elif c5 > 0x1F:
            c5 = 0x1F
        out.append(0x8000 | (c5 << 10) | (c5 << 5) | c5)
    return out


@dataclass(slots=True)
class Lights:
    """UltimaSDK-style access to light.mul/lightidx.mul."""

    file_index: FileIndex

    @classmethod
    def from_files(cls, files: "Files") -> "Lights":
        return cls(file_index=files.file_index("light"))

    def read_light_raw(self, index: int) -> tuple[bytes, int, int] | None:
        res = self.file_index.seek(index)
        if res is None:
            return None

        stream, length, extra, _patched = res
        try:
            raw = stream.read(length)
        finally:
            stream.close()

        dims = _dims_from_extra(length, extra)
        if dims is None:
            return None
        w, h = dims
        if len(raw) != w * h:
            # Corrupt entry; avoid inconsistent shapes.
            return None

        return raw, w, h

    def light_pixels_1555(self, index: int) -> tuple[int, int, list[int]] | None:
        rr = self.read_light_raw(index)
        if rr is None:
            return None
        raw, w, h = rr
        try:
            pixels = decode_light_to_1555(raw)
        except Exception as e:
            raise MulFormatError(str(e)) from e
        if len(pixels) != w * h:
            return None
        return w, h, pixels

    def export_light(self, index: int, out_path: str) -> bool:
        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for image export. Install Pillow or `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        decoded = self.light_pixels_1555(index)
        if decoded is None:
            return False
        w, h, pixels = decoded

        from .art_codec import pixels1555_to_pil_rgba

        img = pixels1555_to_pil_rgba(w, h, pixels)
        img.save(out_path)
        return True


if TYPE_CHECKING:
    from .files import Files
