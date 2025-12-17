from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Iterable, Sequence

from ..errors import MulFormatError


_MULTI_OLD_STRUCT = struct.Struct("<HhhhI")  # item_id:u16, x:i16, y:i16, z:i16, flags:u32
_MULTI_NEW_STRUCT = struct.Struct("<HhhhQ")  # item_id:u16, x:i16, y:i16, z:i16, flags:u64


@dataclass(frozen=True, slots=True)
class MultiTileEntry:
    item_id: int
    offset_x: int
    offset_y: int
    offset_z: int
    flags: int


def decode_multi_tiles(raw: bytes) -> tuple[list[MultiTileEntry], bool]:
    """Decode a multi record payload into tile entries.

    Returns (tiles, use_new_format).

    Format is inferred from payload sizing:
    - Old: 12 bytes per tile (u32 flags)
    - New: 16 bytes per tile (u64 flags)
    """

    if not raw:
        return [], False

    use_new = False
    if len(raw) % _MULTI_OLD_STRUCT.size == 0:
        entry_struct = _MULTI_OLD_STRUCT
        use_new = False
    elif len(raw) % _MULTI_NEW_STRUCT.size == 0:
        entry_struct = _MULTI_NEW_STRUCT
        use_new = True
    else:
        raise MulFormatError("multi record has unexpected size")

    tiles: list[MultiTileEntry] = []
    for off in range(0, len(raw), entry_struct.size):
        item_id, x, y, z, flags = entry_struct.unpack_from(raw, off)
        tiles.append(
            MultiTileEntry(
                item_id=int(item_id) & 0xFFFF,
                offset_x=int(x),
                offset_y=int(y),
                offset_z=int(z),
                flags=int(flags),
            )
        )

    return tiles, use_new


def encode_multi_tiles(tiles: Sequence[MultiTileEntry], *, use_new_format: bool) -> bytes:
    entry_struct = _MULTI_NEW_STRUCT if use_new_format else _MULTI_OLD_STRUCT

    out = bytearray(entry_struct.size * len(tiles))
    off = 0
    for t in tiles:
        if use_new_format:
            entry_struct.pack_into(
                out,
                off,
                int(t.item_id) & 0xFFFF,
                int(t.offset_x),
                int(t.offset_y),
                int(t.offset_z),
                int(t.flags) & 0xFFFFFFFFFFFFFFFF,
            )
        else:
            entry_struct.pack_into(
                out,
                off,
                int(t.item_id) & 0xFFFF,
                int(t.offset_x),
                int(t.offset_y),
                int(t.offset_z),
                int(t.flags) & 0xFFFFFFFF,
            )
        off += entry_struct.size
    return bytes(out)


def _center_tiles_in_place(tiles: list[MultiTileEntry]) -> list[MultiTileEntry]:
    """Match UltimaSDK import behavior: recenters by subtracting computed center."""

    if not tiles:
        return tiles

    min_x = min(t.offset_x for t in tiles)
    max_x = max(t.offset_x for t in tiles)
    min_y = min(t.offset_y for t in tiles)
    max_y = max(t.offset_y for t in tiles)

    center_x = int(max_x - round((max_x - min_x) / 2.0))
    center_y = int(max_y - round((max_y - min_y) / 2.0))

    if center_x == 0 and center_y == 0:
        return tiles

    return [
        MultiTileEntry(
            item_id=t.item_id,
            offset_x=int(t.offset_x - center_x),
            offset_y=int(t.offset_y - center_y),
            offset_z=t.offset_z,
            flags=t.flags,
        )
        for t in tiles
    ]


def parse_multi_txt(text: str) -> list[MultiTileEntry]:
    """Parse UltimaSDK-style multi TXT.

    Each line:
        0x<hex_item_id> <x> <y> <z> <flags>
    """

    tiles: list[MultiTileEntry] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue

        item_raw = parts[0].lower().replace("0x", "")
        try:
            item_id = int(item_raw, 16)
            x = int(parts[1])
            y = int(parts[2])
            z = int(parts[3])
            flags = int(parts[4])
        except Exception:
            continue

        tiles.append(MultiTileEntry(item_id=item_id, offset_x=x, offset_y=y, offset_z=z, flags=flags))

    return _center_tiles_in_place(tiles)


def format_multi_txt(tiles: Iterable[MultiTileEntry]) -> str:
    lines = []
    for t in tiles:
        lines.append(f"0x{int(t.item_id):X} {int(t.offset_x)} {int(t.offset_y)} {int(t.offset_z)} {int(t.flags)}")
    return "\n".join(lines) + ("\n" if lines else "")


def parse_multi_uoa(text: str) -> list[MultiTileEntry]:
    """Parse Ultima Online Architect (UOA) text export.

    Format (UltimaSDK): 4 header lines, then `<count>` component lines:
        <itemid> <x> <y> <z> <flags>
    """

    lines = [ln.rstrip("\r") for ln in text.splitlines()]
    if len(lines) < 4:
        return []

    # 4th line begins with count.
    try:
        count = int(lines[3].split()[0])
    except Exception:
        return []

    tiles: list[MultiTileEntry] = []
    for ln in lines[4 : 4 + count]:
        parts = ln.split()
        if len(parts) < 5:
            continue
        try:
            item_id = int(parts[0])
            x = int(parts[1])
            y = int(parts[2])
            z = int(parts[3])
            flags = int(parts[4])
        except Exception:
            continue
        tiles.append(MultiTileEntry(item_id=item_id, offset_x=x, offset_y=y, offset_z=z, flags=flags))

    return _center_tiles_in_place(tiles)


def format_multi_uoa(tiles: Sequence[MultiTileEntry]) -> str:
    lines = [
        "6 version",
        "1 template id",
        "-1 item version",
        f"{len(tiles)} num components",
    ]
    for t in tiles:
        lines.append(
            f"{int(t.item_id)} {int(t.offset_x)} {int(t.offset_y)} {int(t.offset_z)} {int(t.flags)}"
        )
    return "\n".join(lines) + "\n"


def parse_multi_wsc(text: str) -> list[MultiTileEntry]:
    """Parse a WSC decoration file exported by UltimaSDK.

    We read only SECTION WORLDITEM blocks, and only ID/X/Y/Z fields.
    Flags are set to Background (matches UltimaSDK importer).
    """

    tiles: list[MultiTileEntry] = []
    current: dict[str, int] = {}

    def flush() -> None:
        nonlocal current
        if "id" in current:
            tiles.append(
                MultiTileEntry(
                    item_id=int(current.get("id", 0)) & 0xFFFF,
                    offset_x=int(current.get("x", 0)),
                    offset_y=int(current.get("y", 0)),
                    offset_z=int(current.get("z", 0)),
                    flags=1,  # TileFlag.Background
                )
            )
        current = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("SECTION WORLDITEM"):
            flush()
            continue
        if line.startswith("ID"):
            try:
                current["id"] = int(line[2:].strip())
            except Exception:
                pass
        elif line.startswith("X"):
            try:
                current["x"] = int(line[1:].strip())
            except Exception:
                pass
        elif line.startswith("Y"):
            try:
                current["y"] = int(line[1:].strip())
            except Exception:
                pass
        elif line.startswith("Z"):
            try:
                current["z"] = int(line[1:].strip())
            except Exception:
                pass

    flush()
    return _center_tiles_in_place(tiles)


def format_multi_wsc(tiles: Sequence[MultiTileEntry]) -> str:
    lines: list[str] = []
    for i, t in enumerate(tiles):
        lines.append(f"SECTION WORLDITEM {i}")
        lines.append("{")
        lines.append(f"\tID\t{int(t.item_id)}")
        lines.append(f"\tX\t{int(t.offset_x)}")
        lines.append(f"\tY\t{int(t.offset_y)}")
        lines.append(f"\tZ\t{int(t.offset_z)}")
        lines.append("\tColor\t0")
        lines.append("}")
    return "\n".join(lines) + ("\n" if lines else "")
