from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

from ..errors import MulIndexOutOfRange
from .idx import IdxEntry, read_idx_entries, write_idx_entries


@dataclass(slots=True)
class MulPair:
    """Generic `{type}.mul` + `{type}idx.mul` pair.

    This provides *raw* record access.
    Higher-level codecs (art/gumps/sound/etc.) can be layered on top.
    """

    mul_path: Path
    idx_path: Path

    def load_index(self) -> list[IdxEntry]:
        with self.idx_path.open("rb") as f:
            return read_idx_entries(f)

    def save_index(self, entries: list[IdxEntry]) -> None:
        self.idx_path.parent.mkdir(parents=True, exist_ok=True)
        with self.idx_path.open("wb") as f:
            write_idx_entries(f, entries)

    def read_raw(self, index: int, *, entries: list[IdxEntry] | None = None) -> bytes | None:
        if entries is None:
            entries = self.load_index()
        if index < 0 or index >= len(entries):
            raise MulIndexOutOfRange(index)

        entry = entries[index]
        if entry.is_empty:
            return None

        with self.mul_path.open("rb") as data:
            data.seek(entry.offset)
            return data.read(entry.decoded_length)

    def append_raw(
        self,
        payload: bytes,
        *,
        extra: int = 0,
        index: int | None = None,
        entries: list[IdxEntry] | None = None,
    ) -> tuple[int, list[IdxEntry]]:
        """Append a new record to the data file and update the index.

        If `index` is None, appends a new entry at the end.
        If `index` is provided, replaces that entry by appending payload and
        updating its offset/length.
        """

        if entries is None:
            entries = self.load_index() if self.idx_path.exists() else []

        self.mul_path.parent.mkdir(parents=True, exist_ok=True)
        with self.mul_path.open("ab") as data:
            data.seek(0, 2)
            offset = data.tell()
            data.write(payload)

        new_entry = IdxEntry(offset=offset, length=len(payload), extra=extra)

        if index is None:
            entries.append(new_entry)
            return len(entries) - 1, entries

        if index < 0:
            raise MulIndexOutOfRange(index)
        if index >= len(entries):
            # Grow with empty entries up to the requested index.
            entries.extend([IdxEntry(-1, -1, 0)] * (index - len(entries) + 1))
        entries[index] = new_entry
        return index, entries

    def open_files(self, mode: str = "rb") -> tuple[BinaryIO, BinaryIO]:
        """Open (idx, mul) for advanced scenarios."""

        return (
            cast(BinaryIO, self.idx_path.open(mode)),
            cast(BinaryIO, self.mul_path.open(mode)),
        )
