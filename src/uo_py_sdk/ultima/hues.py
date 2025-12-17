from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ..errors import MulFormatError


_HUE_COUNT = 3000
_HUES_PER_BLOCK = 8
_BLOCK_COUNT = 375
_NAME_BYTES = 20


@dataclass(slots=True)
class Hue:
    index: int
    colors: list[int]  # 32 entries, u16 hue colors
    table_start: int = 0
    table_end: int = 0
    name: str = ""

    def apply_to_pixels1555(self, pixels_1555: list[int], *, only_hue_gray_pixels: bool) -> list[int]:
        out = list(pixels_1555)
        for i, c in enumerate(out):
            if c == 0:
                continue
            r = (c >> 10) & 0x1F
            g = (c >> 5) & 0x1F
            b = c & 0x1F
            if only_hue_gray_pixels and not (r == g == b):
                continue
            out[i] = int(self.colors[r]) & 0xFFFF
        return out


@dataclass(slots=True)
class Hues:
    """UltimaSDK-style hues.mul loader.

    `hues.mul` is not an IDX/MUL pair; it is a single structured file.
    """

    hues: list[Hue]

    @classmethod
    def from_path(cls, hues_mul: str | Path) -> "Hues":
        path = Path(hues_mul)
        if not path.exists():
            return cls(hues=[Hue(i, [0] * 32) for i in range(3000)])

        data = path.read_bytes()

        # Each block is 708 bytes:
        # - 4 bytes header (int32)
        # - 8 entries of 88 bytes each
        block_size = 708
        block_count = min(len(data) // block_size, 375)

        hues: list[Hue] = []
        off = 0
        index = 0
        for _ in range(block_count):
            if off + block_size > len(data):
                break
            _header = struct.unpack_from("<i", data, off)[0]
            off += 4

            for _j in range(8):
                if off + 88 > len(data):
                    raise MulFormatError("hues.mul truncated")

                colors_raw = struct.unpack_from("<32H", data, off)
                off += 64
                table_start, table_end = struct.unpack_from("<HH", data, off)
                off += 4
                name_bytes = data[off : off + 20]
                off += 20

                colors = [int(c) ^ 0x8000 for c in colors_raw]
                table_start ^= 0x8000
                table_end ^= 0x8000

                name = name_bytes.split(b"\x00", 1)[0].decode("latin-1", errors="replace").strip()
                hues.append(
                    Hue(
                        index=index,
                        colors=colors,
                        table_start=int(table_start),
                        table_end=int(table_end),
                        name=name,
                    )
                )
                index += 1

        for i in range(index, 3000):
            hues.append(Hue(i, [0] * 32))

        return cls(hues=hues)

    def get_hue(self, index: int) -> Hue:
        index &= 0x3FFF
        if 0 <= index < len(self.hues):
            return self.hues[index]
        return self.hues[0]

    def save(self, out_path: str | Path) -> None:
        """Write a `hues.mul` file.

        This writes exactly 3000 hues (375 blocks x 8 entries) to match
        the classic client layout.
        """

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Normalize to exactly 3000 hues.
        hues: list[Hue] = list(self.hues)
        if len(hues) < _HUE_COUNT:
            for i in range(len(hues), _HUE_COUNT):
                hues.append(Hue(i, [0] * 32))
        elif len(hues) > _HUE_COUNT:
            hues = hues[:_HUE_COUNT]

        with out.open("wb") as f:
            index = 0
            for _ in range(_BLOCK_COUNT):
                # UltimaSDK exposes this header but it is typically unused.
                f.write(struct.pack("<i", 0))

                for _j in range(_HUES_PER_BLOCK):
                    h = hues[index]
                    if len(h.colors) != 32:
                        raise ValueError(f"hue {index} must have exactly 32 colors")

                    colors_raw = [(int(c) & 0xFFFF) ^ 0x8000 for c in h.colors]
                    f.write(struct.pack("<32H", *colors_raw))
                    f.write(struct.pack("<HH", (int(h.table_start) & 0xFFFF) ^ 0x8000, (int(h.table_end) & 0xFFFF) ^ 0x8000))

                    name = (h.name or "").encode("latin-1", errors="replace")
                    name = name[:_NAME_BYTES].ljust(_NAME_BYTES, b"\x00")
                    f.write(name)

                    index += 1
