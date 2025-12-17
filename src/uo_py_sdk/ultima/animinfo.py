from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ..errors import MulFormatError


@dataclass(slots=True)
class AnimInfoEntry:
    unk1: int
    unk2: int


@dataclass(slots=True)
class AnimInfo:
    """Minimal animinfo.mul loader.

    `animinfo.mul` appears to be a flat table of fixed-size records.

    This repo's fixtures use 4000 bytes, which corresponds to 1000 records of:
    - uint16 unk1
    - uint16 unk2

    (No UltimaSDK reference for this file exists in the embedded C# tree, so this
    keeps parsing conservative and exposes the raw fields.)
    """

    entries: list[AnimInfoEntry]

    @classmethod
    def from_path(cls, animinfo_mul: str | Path) -> "AnimInfo":
        p = Path(animinfo_mul)
        if not p.exists():
            return cls(entries=[])

        data = p.read_bytes()
        if len(data) % 4 != 0:
            raise MulFormatError("animinfo.mul has an unexpected size")

        entries: list[AnimInfoEntry] = []
        for unk1, unk2 in struct.iter_unpack("<HH", data):
            entries.append(AnimInfoEntry(unk1=int(unk1), unk2=int(unk2)))

        return cls(entries=entries)

    def get(self, index: int) -> AnimInfoEntry | None:
        index = int(index)
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None

    def save(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f:
            for e in self.entries:
                f.write(struct.pack("<HH", int(e.unk1) & 0xFFFF, int(e.unk2) & 0xFFFF))
