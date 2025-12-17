from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from ..errors import MulFormatError


@dataclass(frozen=True, slots=True)
class AsciiGlyph:
    width: int
    height: int
    unk: int
    pixels_1555: list[int]


@dataclass(slots=True)
class AsciiFont:
    """One of the 10 fonts embedded in `fonts.mul` (UltimaSDK ASCIIText)."""

    header: int
    glyphs: list[AsciiGlyph]

    def glyph_index(self, ch: str) -> int:
        if not ch:
            return 0
        # UltimaSDK maps 0x20.. to 224 glyphs.
        return ((ord(ch[0]) - 0x20) & 0x7FFFFFFF) % 224

    def glyph(self, ch: str) -> AsciiGlyph:
        return self.glyphs[self.glyph_index(ch)]

    def text_width(self, text: str) -> int:
        return sum(self.glyph(ch).width for ch in (text or ""))

    def render_text(self, text: str):
        """Render ASCII text to a PIL RGBA image (requires Pillow)."""

        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for font rendering. Install `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        from .art_codec import pixels1555_to_pil_rgba

        text = text or ""
        width = self.text_width(text) + 2
        height = max((g.height for g in self.glyphs[:96] if g.height > 0), default=0) + 2
        img = Image.new("RGBA", (max(width, 1), max(height, 1)))

        dx = 2
        dy = height
        for ch in text:
            g = self.glyph(ch)
            if g.width <= 0 or g.height <= 0:
                continue
            glyph_img = pixels1555_to_pil_rgba(g.width, g.height, g.pixels_1555)
            img.paste(glyph_img, (dx, dy - g.height), glyph_img)
            dx += g.width

        return img


@dataclass(slots=True)
class AsciiFonts:
    """Loader/writer for `fonts.mul` containing 10 ASCII fonts."""

    fonts: list[AsciiFont]

    @classmethod
    def from_path(cls, fonts_mul: str | Path) -> "AsciiFonts":
        path = Path(fonts_mul)
        if not path.exists():
            raise FileNotFoundError(str(path))

        data = path.read_bytes()
        off = 0

        fonts: list[AsciiFont] = []
        for _font_id in range(10):
            if off + 1 > len(data):
                raise MulFormatError("fonts.mul truncated (missing header)")
            header = data[off]
            off += 1

            glyphs: list[AsciiGlyph] = []
            for _ in range(224):
                if off + 3 > len(data):
                    raise MulFormatError("fonts.mul truncated (glyph header)")
                width = data[off]
                height = data[off + 1]
                unk = data[off + 2]
                off += 3

                pixels: list[int] = []
                if width > 0 and height > 0:
                    count = int(width) * int(height)
                    byte_len = count * 2
                    if off + byte_len > len(data):
                        raise MulFormatError("fonts.mul truncated (glyph pixels)")

                    # Stored as little-endian u16; non-zero values are XOR 0x8000.
                    for i in range(count):
                        (raw,) = struct.unpack_from("<H", data, off + (i * 2))
                        if raw == 0:
                            pixels.append(0)
                        else:
                            pixels.append((int(raw) ^ 0x8000) & 0xFFFF)

                    off += byte_len

                glyphs.append(AsciiGlyph(width=int(width), height=int(height), unk=int(unk), pixels_1555=pixels))

            fonts.append(AsciiFont(header=int(header), glyphs=glyphs))

        return cls(fonts=fonts)

    @classmethod
    def from_files(cls, files: "Files") -> "AsciiFonts":
        p = files.get_file_path("fonts.mul")
        if p is None:
            raise FileNotFoundError("fonts.mul")
        return cls.from_path(p)

    def save(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if len(self.fonts) != 10:
            raise ValueError("fonts.mul must contain exactly 10 fonts")

        with out.open("wb") as f:
            for font in self.fonts:
                f.write(bytes([int(font.header) & 0xFF]))
                if len(font.glyphs) != 224:
                    raise ValueError("each ASCII font must have exactly 224 glyphs")

                for g in font.glyphs:
                    f.write(bytes([int(g.width) & 0xFF, int(g.height) & 0xFF, int(g.unk) & 0xFF]))

                    if g.width <= 0 or g.height <= 0:
                        continue

                    expected = int(g.width) * int(g.height)
                    if len(g.pixels_1555) != expected:
                        raise ValueError("glyph pixels_1555 length does not match width*height")

                    for px in g.pixels_1555:
                        v = int(px) & 0xFFFF
                        if v == 0:
                            f.write(struct.pack("<H", 0))
                        else:
                            f.write(struct.pack("<H", v ^ 0x8000))


@dataclass(frozen=True, slots=True)
class UnicodeGlyph:
    x_offset: int
    y_offset: int
    width: int
    height: int
    data: bytes | None  # 1bpp rows, packed MSB-first

    def is_pixel_set(self, x: int, y: int) -> bool:
        if self.data is None or self.width <= 0 or self.height <= 0:
            return False
        stride = (self.width + 7) // 8
        offset = (x // 8) + (y * stride)
        if offset < 0 or offset >= len(self.data):
            return False
        return (self.data[offset] & (1 << (7 - (x % 8)))) != 0

    def pixels_1555(self) -> list[int]:
        if self.width <= 0 or self.height <= 0 or self.data is None:
            return []
        out: list[int] = [0] * (self.width * self.height)
        for y in range(self.height):
            for x in range(self.width):
                if self.is_pixel_set(x, y):
                    out[y * self.width + x] = 0x8000
        return out

    def image(self):
        """Render glyph as a PIL RGBA image (requires Pillow)."""

        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for font rendering. Install `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        from .art_codec import pixels1555_to_pil_rgba

        if self.width <= 0 or self.height <= 0:
            return None
        px = self.pixels_1555()
        return pixels1555_to_pil_rgba(self.width, self.height, px)


@dataclass(slots=True)
class UnicodeFont:
    """Loader/writer for `unifont*.mul` files (UltimaSDK UnicodeFonts)."""

    glyphs: list[UnicodeGlyph | None]  # length 0x10000

    @classmethod
    def from_path(cls, unifont_mul: str | Path) -> "UnicodeFont":
        path = Path(unifont_mul)
        if not path.exists():
            raise FileNotFoundError(str(path))

        data = path.read_bytes()
        if len(data) < 0x10000 * 4:
            raise MulFormatError("unifont.mul truncated (missing offset table)")

        glyphs: list[UnicodeGlyph | None] = [None] * 0x10000

        for codepoint in range(0x10000):
            (ptr,) = struct.unpack_from("<i", data, codepoint * 4)
            if ptr <= 0 or ptr >= len(data):
                continue
            if ptr + 4 > len(data):
                continue

            x_off = struct.unpack_from("<b", data, ptr)[0]
            y_off = struct.unpack_from("<b", data, ptr + 1)[0]
            width = data[ptr + 2]
            height = data[ptr + 3]

            if width == 0 or height == 0:
                glyphs[codepoint] = UnicodeGlyph(
                    x_offset=int(x_off),
                    y_offset=int(y_off),
                    width=int(width),
                    height=int(height),
                    data=None,
                )
                continue

            stride = ((int(width) - 1) // 8) + 1
            byte_len = int(height) * int(stride)
            start = ptr + 4
            end = start + byte_len
            if end > len(data):
                continue

            glyphs[codepoint] = UnicodeGlyph(
                x_offset=int(x_off),
                y_offset=int(y_off),
                width=int(width),
                height=int(height),
                data=data[start:end],
            )

        return cls(glyphs=glyphs)

    @classmethod
    def from_files(cls, files: "Files", *, font_id: int = 0) -> "UnicodeFont":
        p = files.get_file_path(unifont_filename(font_id))
        if p is None:
            raise FileNotFoundError(unifont_filename(font_id))
        return cls.from_path(p)

    def glyph(self, codepoint: int) -> UnicodeGlyph:
        cp = int(codepoint) & 0xFFFF
        g = self.glyphs[cp]
        if g is not None:
            return g
        return UnicodeGlyph(x_offset=0, y_offset=0, width=0, height=0, data=None)

    def text_size(self, text: str) -> tuple[int, int]:
        text = text or ""
        width = 0
        height = 0
        for ch in text:
            g = self.glyph(ord(ch))
            width += g.width + g.x_offset
            height = max(height, g.height + g.y_offset)
        return width, height

    def render_text(self, text: str):
        """Render Unicode text to a PIL RGBA image (requires Pillow)."""

        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for font rendering. Install `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        from .art_codec import pixels1555_to_pil_rgba

        w, h = self.text_size(text)
        img = Image.new("RGBA", (max(w + 2, 1), max(h + 2, 1)))

        dx = 2
        dy = 2
        for ch in (text or ""):
            g = self.glyph(ord(ch))
            if g.width <= 0 or g.height <= 0 or g.data is None:
                continue
            glyph_img = pixels1555_to_pil_rgba(g.width, g.height, g.pixels_1555())
            dx += int(g.x_offset)
            img.paste(glyph_img, (dx, dy + int(g.y_offset)), glyph_img)
            dx += g.width

        return img

    def save(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if len(self.glyphs) != 0x10000:
            raise ValueError("UnicodeFont must have exactly 0x10000 glyph slots")

        # Build the offset table up-front and then write records sequentially.
        # This avoids per-glyph seeks, which can be very slow for large fonts.
        table_size = 0x10000 * 4
        offsets: list[int] = [0] * 0x10000

        pos = table_size + 4  # table + trailing int32 zero (UltimaSDK convention)
        for cp, g in enumerate(self.glyphs):
            if g is None or g.data is None or g.width == 0 or g.height == 0:
                continue

            stride = ((int(g.width) - 1) // 8) + 1
            expected = int(g.height) * int(stride)
            if len(g.data) != expected:
                raise ValueError("unicode glyph data length does not match width/height")

            offsets[cp] = pos
            pos += 4 + expected  # header (x,y,w,h) + bitmap bytes

        table = bytearray(table_size)
        for cp, off in enumerate(offsets):
            struct.pack_into("<i", table, cp * 4, int(off))

        with out.open("wb") as f:
            f.write(table)
            f.write(struct.pack("<i", 0))

            for cp, g in enumerate(self.glyphs):
                if offsets[cp] == 0 or g is None or g.data is None or g.width == 0 or g.height == 0:
                    continue

                f.write(struct.pack("<b", int(g.x_offset)))
                f.write(struct.pack("<b", int(g.y_offset)))
                f.write(bytes([int(g.width) & 0xFF, int(g.height) & 0xFF]))
                f.write(g.data)


@dataclass(slots=True)
class UnicodeFonts:
    """Container for the 13 possible `unifont*.mul` files (UltimaSDK-style)."""

    fonts: list[UnicodeFont | None]  # length 13

    @classmethod
    def from_files(cls, files: "Files") -> "UnicodeFonts":
        loaded: list[UnicodeFont | None] = []
        for font_id in range(13):
            p = files.get_file_path(unifont_filename(font_id))
            loaded.append(UnicodeFont.from_path(p) if p is not None else None)
        return cls(fonts=loaded)

    def get(self, font_id: int) -> UnicodeFont | None:
        fid = int(font_id)
        if 0 <= fid < len(self.fonts):
            return self.fonts[fid]
        return None

    def require(self, font_id: int) -> UnicodeFont:
        font = self.get(font_id)
        if font is None:
            raise FileNotFoundError(unifont_filename(font_id))
        return font

    def save(self, out_dir: str | Path) -> list[Path]:
        """Write any loaded `unifont*.mul` files into `out_dir`.

        Returns the list of written file paths.
        """

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        for font_id, font in enumerate(self.fonts):
            if font is None:
                continue
            p = out / unifont_filename(font_id)
            font.save(p)
            written.append(p)
        return written


def unifont_filename(font_id: int) -> str:
    """Return Ultima-style unifont file name for a Unicode font id (0..12)."""

    fid = int(font_id)
    if fid < 0 or fid > 12:
        raise ValueError("font_id must be 0..12")
    return "unifont.mul" if fid == 0 else f"unifont{fid}.mul"


def find_first_renderable_unicode_glyph(font: UnicodeFont, *, start: int = 0) -> tuple[int, UnicodeGlyph] | None:
    for cp in range(int(start) & 0xFFFF, 0x10000):
        g = font.glyph(cp)
        if g.width > 0 and g.height > 0 and g.data is not None:
            return cp, g
    return None


def find_first_renderable_ascii_glyph(font: AsciiFont, *, start_index: int = 0) -> tuple[int, AsciiGlyph] | None:
    for i in range(max(0, int(start_index)), 224):
        g = font.glyphs[i]
        if g.width > 0 and g.height > 0 and g.pixels_1555:
            return i, g
    return None


if TYPE_CHECKING:
    from .files import Files
