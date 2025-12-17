from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ..errors import MulFormatError


@dataclass(frozen=True, slots=True)
class SkillGroup:
    name: str


@dataclass(slots=True)
class SkillGroups:
    """UltimaSDK-style loader for skillgrp.mul.

    File layout (per UltimaSDK SkillGroups.cs):
    - int32 count OR (-1, int32 count) to indicate unicode
    - fixed-size null-terminated group name blocks (excluding the implicit "Misc")
      - ANSI: 17 bytes each
      - Unicode: 34 bytes each
    - trailing int32 list mapping skills to group ids (until EOF)

    UltimaSDK always adds a synthetic "Misc" group at index 0.
    """

    groups: list[SkillGroup]
    skill_list: list[int]
    is_unicode: bool

    @classmethod
    def from_path(cls, skillgrp_mul: str | Path) -> "SkillGroups":
        path = Path(skillgrp_mul)
        if not path.exists():
            return cls(groups=[SkillGroup("Misc")], skill_list=[], is_unicode=False)

        data = path.read_bytes()
        if len(data) < 4:
            raise MulFormatError("skillgrp.mul truncated")

        off = 0
        (count,) = struct.unpack_from("<i", data, off)
        off += 4

        is_unicode = False
        start = 4
        strlen = 17
        if count == -1:
            is_unicode = True
            if len(data) < 8:
                raise MulFormatError("skillgrp.mul truncated")
            (count,) = struct.unpack_from("<i", data, off)
            off += 4
            start *= 2
            strlen *= 2

        if count <= 0:
            return cls(groups=[SkillGroup("Misc")], skill_list=[], is_unicode=is_unicode)

        groups: list[SkillGroup] = [SkillGroup("Misc")]

        # Read count-1 group names from fixed-width slots.
        for i in range(0, int(count) - 1):
            slot_off = start + (i * strlen)
            if slot_off >= len(data):
                break
            slot = data[slot_off : min(len(data), slot_off + strlen)]

            if is_unicode:
                # UTF-16LE null-terminated
                name = slot.decode("utf-16le", errors="replace").split("\x00", 1)[0]
            else:
                name = slot.split(b"\x00", 1)[0].decode("cp1252", errors="replace")

            name = name.strip()
            groups.append(SkillGroup(name))

        # Read trailing int32 list.
        skill_list: list[int] = []
        list_off = start + ((int(count) - 1) * strlen)
        if 0 <= list_off < len(data):
            # Clamp to whole int32s (relative to list_off).
            tail_len = ((len(data) - list_off) // 4) * 4
            tail = data[list_off : list_off + tail_len]
            for j in range(0, len(tail), 4):
                (v,) = struct.unpack_from("<i", tail, j)
                skill_list.append(int(v))

        return cls(groups=groups, skill_list=skill_list, is_unicode=is_unicode)
