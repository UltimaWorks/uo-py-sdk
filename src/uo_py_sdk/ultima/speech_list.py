from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ..errors import MulFormatError


@dataclass(frozen=True, slots=True)
class SpeechEntry:
    id: int
    keyword: str
    order: int


@dataclass(slots=True)
class SpeechList:
    """UltimaSDK-style speech.mul loader.

    `speech.mul` is a single structured file containing repeating entries:
    - id: u16 (big-endian / swapped endian in UltimaSDK)
    - length: u16 (big-endian / swapped endian)
    - keyword: UTF-8 bytes of length `length`

    UltimaSDK clamps `length` to 128 when reading.
    """

    entries: list[SpeechEntry]

    @classmethod
    def from_path(cls, speech_mul: str | Path) -> "SpeechList":
        path = Path(speech_mul)
        if not path.exists():
            return cls(entries=[])

        data = path.read_bytes()
        off = 0
        order = 0
        entries: list[SpeechEntry] = []

        # Each entry starts with 4 bytes.
        while off < len(data):
            if off + 4 > len(data):
                raise MulFormatError("speech.mul truncated")

            (raw_id,) = struct.unpack_from(">H", data, off)
            (raw_len,) = struct.unpack_from(">H", data, off + 2)
            off += 4

            length = min(int(raw_len), 128)
            if off + length > len(data):
                raise MulFormatError("speech.mul truncated")

            keyword_bytes = data[off : off + length]
            off += length

            keyword = keyword_bytes.decode("utf-8", errors="replace")
            entries.append(SpeechEntry(id=int(raw_id), keyword=keyword, order=order))
            order += 1

        return cls(entries=entries)
