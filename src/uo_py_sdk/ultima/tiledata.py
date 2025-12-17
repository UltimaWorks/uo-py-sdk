from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ..errors import MulFormatError


_LAND_COUNT = 0x4000
_GROUP_SIZE = 32
_NAME_BYTES = 20


# Record layouts match UltimaSDK (see Ultima/TileData.cs)
_OLD_LAND_STRUCT = struct.Struct("<ih20s")  # flags:int32, tex_id:int16, name[20]
_NEW_LAND_STRUCT = struct.Struct("<iih20s")  # flags:int32, unk1:int32, tex_id:int16, name[20]

_OLD_ITEM_STRUCT = struct.Struct("<iBBhBBhBBBBB20s")
# flags:int32, weight:u8, quality:u8, miscdata:i16, unk2:u8, quantity:u8,
# anim:i16, unk3:u8, hue:u8, stackingoffset:u8, value:u8, height:u8, name[20]

_NEW_ITEM_STRUCT = struct.Struct("<iiBBhBBhBBBBB20s")
# flags:int32, unk1:int32, then same as old


@dataclass(slots=True)
class LandTile:
    index: int
    flags: int
    tex_id: int
    name: str
    unk1: int = 0


@dataclass(slots=True)
class ItemTile:
    index: int
    flags: int
    weight: int
    quality: int
    misc_data: int
    unk2: int
    quantity: int
    animation: int
    unk3: int
    hue: int
    stacking_offset: int
    value: int
    height: int
    name: str
    unk1: int = 0


def _decode_name_20(raw: bytes) -> str:
    raw = raw[:_NAME_BYTES]
    raw = raw.split(b"\x00", 1)[0]
    # UltimaSDK uses Encoding.Default; on Windows this is typically cp1252.
    return raw.decode("cp1252", errors="replace")


def _encode_name_20(name: str) -> bytes:
    b = (name or "").encode("cp1252", errors="replace")
    return b[:_NAME_BYTES].ljust(_NAME_BYTES, b"\x00")


def _convert_string_to_int(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    if "0x" in t.lower():
        t = t.lower().replace("0x", "")
        return int(t, 16)
    return int(t, 10)


def _flag_bit(value: int, mask: int) -> str:
    return "1" if (int(value) & int(mask)) != 0 else "0"


# TileFlag masks (Ultima/TileData.cs)
_TILEFLAG_BITS: list[tuple[str, int]] = [
    ("Background", 0x00000001),
    ("Weapon", 0x00000002),
    ("Transparent", 0x00000004),
    ("Translucent", 0x00000008),
    ("Wall", 0x00000010),
    ("Damaging", 0x00000020),
    ("Impassable", 0x00000040),
    ("Wet", 0x00000080),
    ("Unknown1", 0x00000100),
    ("Surface", 0x00000200),
    ("Bridge", 0x00000400),
    ("Generic", 0x00000800),
    ("Window", 0x00001000),
    ("NoShoot", 0x00002000),
    ("ArticleA", 0x00004000),
    ("ArticleAn", 0x00008000),
    ("Internal", 0x00010000),
    ("Foliage", 0x00020000),
    ("PartialHue", 0x00040000),
    ("Unknown2", 0x00080000),
    ("Map", 0x00100000),
    ("Container", 0x00200000),
    ("Wearable", 0x00400000),
    ("LightSource", 0x00800000),
    ("Animation", 0x01000000),
    ("HoverOver", 0x02000000),
    ("Unknown3", 0x04000000),
    ("Armor", 0x08000000),
    ("Roof", 0x10000000),
    ("Door", 0x20000000),
    ("StairBack", 0x40000000),
    ("StairRight", 0x80000000),
]


@dataclass(slots=True)
class TileData:
    """UltimaSDK-style tiledata.mul loader/writer.

    `tiledata.mul` layout:
    - Land section: 0x4000 entries, grouped by 32, each group prefixed by an int32 header
    - Item section: N entries (typically 0x10000), grouped by 32, each group prefixed by an int32 header

    Two formats exist:
    - Old: land/item records begin with int32 flags
    - New: adds an extra int32 `unk1` after flags
    """

    land: list[LandTile]
    items: list[ItemTile]
    land_headers: list[int]
    item_headers: list[int]
    is_new_format: bool

    @classmethod
    def from_path(cls, tiledata_mul: str | Path) -> "TileData":
        path = Path(tiledata_mul)
        if not path.exists():
            raise FileNotFoundError(str(path))

        data = path.read_bytes()
        file_size = len(data)

        # Detect format by validating the item-section block sizing.
        candidates: list[tuple[bool, struct.Struct, struct.Struct]] = [
            (False, _OLD_LAND_STRUCT, _OLD_ITEM_STRUCT),
            (True, _NEW_LAND_STRUCT, _NEW_ITEM_STRUCT),
        ]

        chosen: tuple[bool, struct.Struct, struct.Struct] | None = None
        for is_new, land_struct, item_struct in candidates:
            land_section_size = (4 * (_LAND_COUNT // _GROUP_SIZE)) + (_LAND_COUNT * land_struct.size)
            if file_size < land_section_size:
                continue
            remaining = file_size - land_section_size
            block_size = 4 + (_GROUP_SIZE * item_struct.size)
            if remaining % block_size == 0:
                chosen = (is_new, land_struct, item_struct)
                break

        if chosen is None:
            raise MulFormatError("tiledata.mul has an unexpected size/layout")

        is_new, land_struct, item_struct = chosen

        land_headers: list[int] = []
        item_headers: list[int] = []
        land: list[LandTile] = []
        items: list[ItemTile] = []

        off = 0

        # Land
        for base_index in range(0, _LAND_COUNT, _GROUP_SIZE):
            if off + 4 > file_size:
                raise MulFormatError("tiledata.mul truncated (land header)")
            (hdr,) = struct.unpack_from("<i", data, off)
            off += 4
            land_headers.append(int(hdr))

            for i in range(_GROUP_SIZE):
                if off + land_struct.size > file_size:
                    raise MulFormatError("tiledata.mul truncated (land record)")
                if is_new:
                    flags, unk1, tex_id, name_raw = land_struct.unpack_from(data, off)
                    off += land_struct.size
                    land.append(
                        LandTile(
                            index=base_index + i,
                            flags=int(flags),
                            unk1=int(unk1),
                            tex_id=int(tex_id),
                            name=_decode_name_20(name_raw),
                        )
                    )
                else:
                    flags, tex_id, name_raw = land_struct.unpack_from(data, off)
                    off += land_struct.size
                    land.append(
                        LandTile(
                            index=base_index + i,
                            flags=int(flags),
                            tex_id=int(tex_id),
                            name=_decode_name_20(name_raw),
                        )
                    )

        # Items
        item_count = (file_size - off) // (4 + _GROUP_SIZE * item_struct.size) * _GROUP_SIZE
        for base_index in range(0, item_count, _GROUP_SIZE):
            if off + 4 > file_size:
                raise MulFormatError("tiledata.mul truncated (item header)")
            (hdr,) = struct.unpack_from("<i", data, off)
            off += 4
            item_headers.append(int(hdr))

            for i in range(_GROUP_SIZE):
                if off + item_struct.size > file_size:
                    raise MulFormatError("tiledata.mul truncated (item record)")
                if is_new:
                    (
                        flags,
                        unk1,
                        weight,
                        quality,
                        misc_data,
                        unk2,
                        quantity,
                        animation,
                        unk3,
                        hue,
                        stacking_offset,
                        value,
                        height,
                        name_raw,
                    ) = item_struct.unpack_from(data, off)
                    off += item_struct.size
                    items.append(
                        ItemTile(
                            index=base_index + i,
                            flags=int(flags),
                            unk1=int(unk1),
                            weight=int(weight),
                            quality=int(quality),
                            misc_data=int(misc_data),
                            unk2=int(unk2),
                            quantity=int(quantity),
                            animation=int(animation),
                            unk3=int(unk3),
                            hue=int(hue),
                            stacking_offset=int(stacking_offset),
                            value=int(value),
                            height=int(height),
                            name=_decode_name_20(name_raw),
                        )
                    )
                else:
                    (
                        flags,
                        weight,
                        quality,
                        misc_data,
                        unk2,
                        quantity,
                        animation,
                        unk3,
                        hue,
                        stacking_offset,
                        value,
                        height,
                        name_raw,
                    ) = item_struct.unpack_from(data, off)
                    off += item_struct.size
                    items.append(
                        ItemTile(
                            index=base_index + i,
                            flags=int(flags),
                            weight=int(weight),
                            quality=int(quality),
                            misc_data=int(misc_data),
                            unk2=int(unk2),
                            quantity=int(quantity),
                            animation=int(animation),
                            unk3=int(unk3),
                            hue=int(hue),
                            stacking_offset=int(stacking_offset),
                            value=int(value),
                            height=int(height),
                            name=_decode_name_20(name_raw),
                        )
                    )

        return cls(
            land=land,
            items=items,
            land_headers=land_headers,
            item_headers=item_headers,
            is_new_format=is_new,
        )

    def land_tile(self, tile_id: int) -> LandTile:
        tile_id &= 0x3FFF
        return self.land[tile_id]

    def item_tile(self, tile_id: int) -> ItemTile:
        tile_id &= 0xFFFF
        if 0 <= tile_id < len(self.items):
            return self.items[tile_id]
        raise IndexError(tile_id)

    def save(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        land_struct = _NEW_LAND_STRUCT if self.is_new_format else _OLD_LAND_STRUCT
        item_struct = _NEW_ITEM_STRUCT if self.is_new_format else _OLD_ITEM_STRUCT

        if len(self.land) != _LAND_COUNT:
            raise ValueError(f"land table must have exactly {_LAND_COUNT} entries")

        with out.open("wb") as f:
            # Land section
            hdr_i = 0
            for base_index in range(0, _LAND_COUNT, _GROUP_SIZE):
                header = self.land_headers[hdr_i] if hdr_i < len(self.land_headers) else 0
                hdr_i += 1
                f.write(struct.pack("<i", int(header)))

                for i in range(_GROUP_SIZE):
                    t = self.land[base_index + i]
                    name_raw = _encode_name_20(t.name)
                    if self.is_new_format:
                        f.write(land_struct.pack(int(t.flags), int(t.unk1), int(t.tex_id), name_raw))
                    else:
                        f.write(land_struct.pack(int(t.flags), int(t.tex_id), name_raw))

            # Item section
            hdr_i = 0
            item_count = len(self.items)
            for base_index in range(0, item_count, _GROUP_SIZE):
                header = self.item_headers[hdr_i] if hdr_i < len(self.item_headers) else 0
                hdr_i += 1
                f.write(struct.pack("<i", int(header)))

                for i in range(_GROUP_SIZE):
                    t = self.items[base_index + i]
                    name_raw = _encode_name_20(t.name)
                    if self.is_new_format:
                        f.write(
                            item_struct.pack(
                                int(t.flags),
                                int(t.unk1),
                                int(t.weight) & 0xFF,
                                int(t.quality) & 0xFF,
                                int(t.misc_data),
                                int(t.unk2) & 0xFF,
                                int(t.quantity) & 0xFF,
                                int(t.animation),
                                int(t.unk3) & 0xFF,
                                int(t.hue) & 0xFF,
                                int(t.stacking_offset) & 0xFF,
                                int(t.value) & 0xFF,
                                int(t.height) & 0xFF,
                                name_raw,
                            )
                        )
                    else:
                        f.write(
                            item_struct.pack(
                                int(t.flags),
                                int(t.weight) & 0xFF,
                                int(t.quality) & 0xFF,
                                int(t.misc_data),
                                int(t.unk2) & 0xFF,
                                int(t.quantity) & 0xFF,
                                int(t.animation),
                                int(t.unk3) & 0xFF,
                                int(t.hue) & 0xFF,
                                int(t.stacking_offset) & 0xFF,
                                int(t.value) & 0xFF,
                                int(t.height) & 0xFF,
                                name_raw,
                            )
                        )

    # CSV import/export (compatible with UltimaSDK TileData.Export*ToCSV)

    def export_land_csv(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with out.open("w", encoding="cp1252", newline="") as f:
            f.write("ID;Name;TextureID;HSAUnk1")
            f.write(
                ";Background;Weapon;Transparent;Translucent;Wall;Damage;Impassible;Wet;Unknow1"
                ";Surface;Bridge;Generic;Window;NoShoot;PrefixA;PrefixAn;Internal;Foliage;PartialHue"
                ";Unknow2;Map;Container/Height;Wearable;Lightsource;Animation;HoverOver"
                ";Unknow3;Armor;Roof;Door;StairBack;StairRight\n"
            )

            for t in self.land:
                parts = [
                    f"0x{t.index:04X}",
                    t.name,
                    f"0x{int(t.tex_id) & 0xFFFF:04X}",
                    str(int(t.unk1) if self.is_new_format else 0),
                ]
                flags = int(t.flags)
                # Note: UltimaSDK header uses some misspellings; we keep column order compatible.
                parts.extend(_flag_bit(flags, mask) for _name, mask in _TILEFLAG_BITS)
                f.write(";".join(parts) + "\n")

    def export_item_csv(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with out.open("w", encoding="cp1252", newline="") as f:
            f.write(
                "ID;Name;Weight/Quantity;Layer/Quality;Gump/AnimID;Height;Hue;Class/Quantity;"
                "StackingOffset;MiscData;Unknown1;Unknown2;Unknown3"
            )
            f.write(
                ";Background;Weapon;Transparent;Translucent;Wall;Damage;Impassible;Wet;Unknow1"
                ";Surface;Bridge;Generic;Window;NoShoot;PrefixA;PrefixAn;Internal;Foliage;PartialHue"
                ";Unknow2;Map;Container/Height;Wearable;Lightsource;Animation;HoverOver"
                ";Unknow3;Armor;Roof;Door;StairBack;StairRight\n"
            )

            for t in self.items:
                parts = [
                    f"0x{t.index:04X}",
                    t.name,
                    str(int(t.weight)),
                    str(int(t.quality)),
                    f"0x{int(t.animation) & 0xFFFF:04X}",
                    str(int(t.height)),
                    str(int(t.hue)),
                    str(int(t.quantity)),
                    str(int(t.stacking_offset)),
                    str(int(t.misc_data)),
                    str(int(t.unk1) if self.is_new_format else 0),
                    str(int(t.unk2)),
                    str(int(t.unk3)),
                ]
                flags = int(t.flags)
                parts.extend(_flag_bit(flags, mask) for _name, mask in _TILEFLAG_BITS)
                f.write(";".join(parts) + "\n")

    def import_land_csv(self, csv_path: str | Path) -> None:
        p = Path(csv_path)
        if not p.exists():
            return

        with p.open("r", encoding="cp1252", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("ID;"):
                    continue
                parts = line.split(";")
                if len(parts) < 36:
                    continue

                try:
                    tile_id = _convert_string_to_int(parts[0]) & 0x3FFF
                except Exception:
                    continue

                t = self.land[tile_id]
                # Match UltimaSDK ReadData order.
                t.name = parts[1]
                t.tex_id = _convert_string_to_int(parts[2]) & 0xFFFF
                if self.is_new_format:
                    t.unk1 = _convert_string_to_int(parts[3])

                flags = 0
                for idx, (_name, mask) in enumerate(_TILEFLAG_BITS, start=4):
                    try:
                        if int(parts[idx] or "0") != 0:
                            flags |= mask
                    except Exception:
                        pass
                t.flags = int(flags)

    def import_item_csv(self, csv_path: str | Path) -> None:
        p = Path(csv_path)
        if not p.exists():
            return

        with p.open("r", encoding="cp1252", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("ID;"):
                    continue
                parts = line.split(";")
                if len(parts) < 45:
                    continue

                try:
                    tile_id = _convert_string_to_int(parts[0]) & 0xFFFF
                except Exception:
                    continue
                if tile_id >= len(self.items):
                    continue

                t = self.items[tile_id]
                t.name = parts[1]

                # Mirror UltimaSDK ReadData ordering.
                t.weight = _convert_string_to_int(parts[2]) & 0xFF
                t.quality = _convert_string_to_int(parts[3]) & 0xFF
                t.misc_data = _convert_string_to_int(parts[9])
                if self.is_new_format:
                    t.unk1 = _convert_string_to_int(parts[10])
                t.unk2 = _convert_string_to_int(parts[11]) & 0xFF
                t.quantity = _convert_string_to_int(parts[7]) & 0xFF
                t.animation = _convert_string_to_int(parts[4]) & 0xFFFF
                t.unk3 = _convert_string_to_int(parts[12]) & 0xFF
                t.hue = _convert_string_to_int(parts[6]) & 0xFF
                t.stacking_offset = _convert_string_to_int(parts[8]) & 0xFF
                t.height = _convert_string_to_int(parts[5]) & 0xFF

                # Flags start at index 13 in the exported CSV.
                flags = 0
                for idx, (_name, mask) in enumerate(_TILEFLAG_BITS, start=13):
                    try:
                        if int(parts[idx] or "0") != 0:
                            flags |= mask
                    except Exception:
                        pass
                t.flags = int(flags)
