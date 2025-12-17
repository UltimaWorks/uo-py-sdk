from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import BinaryIO, Iterable

from ..errors import MulFormatError


_IDX_STRUCT = struct.Struct("<iii")  # offset, length, extra
_IDX_ENTRY_SIZE = _IDX_STRUCT.size


@dataclass(frozen=True, slots=True)
class IdxEntry:
    offset: int
    length: int
    extra: int

    @property
    def is_empty(self) -> bool:
        # Convention: unused entries are -1/-1/0 (or -1/-1/-1 in some packs)
        # Note: UltimaSDK uses the high bit of `length` to indicate a verdata patch.
        return self.offset < 0 or self.decoded_length <= 0

    @property
    def is_patched(self) -> bool:
        # High bit indicates verdata patching (UltimaSDK convention)
        return (int(self.length) & 0x80000000) != 0

    @property
    def decoded_length(self) -> int:
        # Mask out the patch flag bit.
        return int(self.length) & 0x7FFFFFFF


def read_idx_entries(fp: BinaryIO) -> list[IdxEntry]:
    """Read IDX entries from `{type}idx.mul`.

    Each entry is 12 bytes: int32 offset, int32 length, int32 extra.
    Reads until EOF.
    """

    if not fp.readable():
        raise ValueError("fp must be readable")

    entries: list[IdxEntry] = []

    # Buffered parsing is dramatically faster than 12-byte reads in a loop,
    # and avoids pathological slowdowns on large fixture IDX files.
    buf = b""
    read_size = _IDX_ENTRY_SIZE * 8192
    while True:
        chunk = fp.read(read_size)
        if not chunk:
            break
        buf += chunk

        excess = len(buf) % _IDX_ENTRY_SIZE
        if excess:
            data = memoryview(buf)[:-excess]
            buf = buf[-excess:]
        else:
            data = memoryview(buf)
            buf = b""

        for off, length, extra in struct.iter_unpack(_IDX_STRUCT.format, data):
            entries.append(IdxEntry(off, length, extra))

    if buf:
        # Leftover bytes that don't make a full entry.
        raise MulFormatError(f"IDX truncated: got {len(buf)} bytes")

    return entries


def write_idx_entries(fp: BinaryIO, entries: Iterable[IdxEntry]) -> None:
    if not fp.writable():
        raise ValueError("fp must be writable")

    for entry in entries:
        fp.write(_IDX_STRUCT.pack(int(entry.offset), int(entry.length), int(entry.extra)))


def read_idx_file(path: str) -> list[IdxEntry]:
    with open(path, "rb") as f:
        return read_idx_entries(f)


def write_idx_file(path: str, entries: Iterable[IdxEntry]) -> None:
    with open(path, "wb") as f:
        write_idx_entries(f, entries)
        f.flush()
        if isinstance(f, io.BufferedWriter):
            try:
                f.raw.flush()
            except Exception:
                pass
