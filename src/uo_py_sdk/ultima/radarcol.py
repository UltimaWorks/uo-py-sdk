from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..errors import MulFormatError


@dataclass(slots=True)
class RadarCol:
    """UltimaSDK-style radarcol.mul loader/writer.

    `radarcol.mul` is a flat array of int16 (little-endian) color values.
    UltimaSDK defaults to 0x8000 entries if the file is missing.

    Indexing conventions:
    - land tiles: [0x0000..]
    - static items: [0x4000..] (land offset applied)
    """

    colors: list[int]

    @classmethod
    def from_path(cls, radarcol_mul: str | Path) -> "RadarCol":
        path = Path(radarcol_mul)
        if not path.exists():
            return cls(colors=[0] * 0x8000)

        data = path.read_bytes()
        if len(data) % 2 != 0:
            raise MulFormatError("radarcol.mul truncated")

        # int16 little-endian entries.
        colors: list[int] = []
        for i in range(0, len(data), 2):
            v = int.from_bytes(data[i : i + 2], "little", signed=True)
            colors.append(v)

        if not colors:
            colors = [0] * 0x8000

        return cls(colors=colors)

    def get_land_color(self, land_id: int) -> int:
        idx = int(land_id) & 0x3FFF
        if 0 <= idx < len(self.colors):
            return int(self.colors[idx])
        return 0

    def get_item_color(self, item_id: int) -> int:
        idx = (int(item_id) & 0x3FFF) + 0x4000
        if 0 <= idx < len(self.colors):
            return int(self.colors[idx])
        return 0

    def set_land_color(self, land_id: int, value: int) -> None:
        idx = int(land_id) & 0x3FFF
        if 0 <= idx < len(self.colors):
            self.colors[idx] = int(value)

    def set_item_color(self, item_id: int, value: int) -> None:
        idx = (int(item_id) & 0x3FFF) + 0x4000
        if 0 <= idx < len(self.colors):
            self.colors[idx] = int(value)

    def save(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Write int16 LE.
        b = bytearray()
        for v in self.colors:
            b += int(v).to_bytes(2, "little", signed=True)
        out.write_bytes(bytes(b))

    def export_csv(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Match UltimaSDK header ordering.
        lines = ["ID;Color"]
        for i, v in enumerate(self.colors):
            lines.append(f"0x{i:04X};{int(v)}")
        out.write_text("\n".join(lines) + "\n", encoding="cp1252", errors="replace")

    def import_csv(self, csv_path: str | Path) -> None:
        p = Path(csv_path)
        if not p.exists():
            return

        # UltimaSDK rebuilds array sized to CSV count; we keep existing sizing
        # and only update indices we can parse and fit.
        for raw in p.read_text(encoding="cp1252", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("ID;"):
                continue
            parts = line.split(";")
            if len(parts) < 2:
                continue
            try:
                idx = int(parts[0].replace("0x", ""), 16) if "0x" in parts[0].lower() else int(parts[0])
                val = int(parts[1].replace("0x", ""), 16) if "0x" in parts[1].lower() else int(parts[1])
            except Exception:
                continue
            if 0 <= idx < len(self.colors):
                self.colors[idx] = int(val)
