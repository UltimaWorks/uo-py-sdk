from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from ..errors import MulFormatError


_ENTRY_STRUCT = struct.Struct("<iiiii")  # file, index, lookup, length, extra


@dataclass(frozen=True, slots=True)
class VerdataPatch:
    file_id: int
    index: int
    lookup: int
    length: int
    extra: int


@dataclass(slots=True)
class Verdata:
    """Represents `verdata.mul` patch table.

    UltimaSDK reads `verdata.mul` and applies matching entries by `file_id`.
    Patched IDX entries are marked by setting the high bit of `length`.
    """

    path: Path | None
    patches: list[VerdataPatch]

    @classmethod
    def from_uo_dir(cls, uo_dir: Path) -> "Verdata":
        path = uo_dir / "verdata.mul"
        if not path.exists():
            # Case-insensitive scan fallback.
            try:
                for child in uo_dir.iterdir():
                    if child.name.lower() == "verdata.mul":
                        path = child
                        break
            except OSError:
                pass

        if not path.exists():
            return cls(path=None, patches=[])

        patches: list[VerdataPatch] = []
        with path.open("rb") as f:
            header = f.read(4)
            if len(header) != 4:
                raise MulFormatError("verdata.mul truncated")
            (count,) = struct.unpack("<i", header)
            if count < 0:
                raise MulFormatError("verdata.mul invalid patch count")

            for _ in range(count):
                chunk = f.read(_ENTRY_STRUCT.size)
                if len(chunk) != _ENTRY_STRUCT.size:
                    raise MulFormatError("verdata.mul truncated patch table")
                file_id, index, lookup, length, extra = _ENTRY_STRUCT.unpack(chunk)
                patches.append(
                    VerdataPatch(
                        file_id=int(file_id),
                        index=int(index),
                        lookup=int(lookup),
                        length=int(length),
                        extra=int(extra),
                    )
                )

        return cls(path=path, patches=patches)

    def open_stream(self) -> BinaryIO:
        if self.path is None:
            raise FileNotFoundError("verdata.mul not found")
        return self.path.open("rb")
