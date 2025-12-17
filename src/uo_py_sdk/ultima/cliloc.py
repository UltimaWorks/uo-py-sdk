from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from enum import IntFlag
from pathlib import Path

from ..errors import MulFormatError


class CliLocFlag(IntFlag):
    Original = 0x0
    Custom = 0x1
    Modified = 0x2


_CLI_RE = re.compile(r"~(\d+)[_\w]+~", flags=re.IGNORECASE | re.DOTALL)


@dataclass(slots=True)
class ClilocEntry:
    number: int
    text: str
    flag: CliLocFlag

    _fmt_txt: str | None = None

    def _get_format_text(self) -> str:
        if self._fmt_txt is None:
            self._fmt_txt = _CLI_RE.sub(r"{\1}", self.text)
        return self._fmt_txt

    def format(self, *args: object) -> str:
        fmt = self._get_format_text()

        # UltimaSDK behavior: args are 1-based (0 is an empty string).
        fmt_args: list[object] = [""] + list(args[:10])
        return fmt.format(*fmt_args)

    def split_format(self, argstr: str) -> str:
        # UltimaSDK uses tab splitting.
        parts = (argstr or "").split("\t")
        return self.format(*parts)


@dataclass(slots=True)
class Cliloc:
    """UltimaSDK-style cliloc loader.

    Format (cliloc.*):
    - int32 header1
    - int16 header2
    - repeating entries until EOF:
      - int32 number
      - byte  flag
      - int16 length
      - `length` bytes UTF-8 text

    The text may contain placeholders like `~1_SOMETHING~`, which UltimaSDK treats as
    positional format slots.
    """

    language: str
    header1: int = 0
    header2: int = 0
    entries: list[ClilocEntry] = None  # type: ignore[assignment]

    _string_table: dict[int, str] | None = None
    _entry_table: dict[int, ClilocEntry] | None = None

    @classmethod
    def from_path(cls, path: str | Path, *, language: str = "") -> "Cliloc":
        p = Path(path)
        if not p.exists():
            return cls(language=str(language), entries=[])

        data = p.read_bytes()
        if len(data) < 6:
            raise MulFormatError("cliloc file truncated")

        header1 = struct.unpack_from("<i", data, 0)[0]
        header2 = struct.unpack_from("<h", data, 4)[0]

        entries: list[ClilocEntry] = []
        string_table: dict[int, str] = {}
        entry_table: dict[int, ClilocEntry] = {}

        off = 6
        while off < len(data):
            if off + 7 > len(data):
                raise MulFormatError("cliloc entry truncated")

            number = struct.unpack_from("<i", data, off)[0]
            off += 4

            flag = data[off]
            off += 1

            length = struct.unpack_from("<h", data, off)[0]
            off += 2

            if length < 0:
                # Be forgiving; skip corrupt entries.
                length = 0

            if off + length > len(data):
                raise MulFormatError("cliloc entry text truncated")

            raw = data[off : off + length]
            off += length

            text = raw.decode("utf-8", errors="replace")
            e = ClilocEntry(number=int(number), text=text, flag=CliLocFlag(int(flag)))
            entries.append(e)
            string_table[int(number)] = text
            entry_table[int(number)] = e

        cl = cls(language=str(language), header1=int(header1), header2=int(header2), entries=entries)
        cl._string_table = string_table
        cl._entry_table = entry_table
        return cl

    def build_index(self) -> None:
        self._string_table = {int(e.number): e.text for e in (self.entries or [])}
        self._entry_table = {int(e.number): e for e in (self.entries or [])}

    def get_string(self, number: int) -> str | None:
        if self._string_table is None:
            self.build_index()
        return None if self._string_table is None else self._string_table.get(int(number))

    def get_entry(self, number: int) -> ClilocEntry | None:
        if self._entry_table is None:
            self.build_index()
        return None if self._entry_table is None else self._entry_table.get(int(number))

    def save(self, out_path: str | Path) -> None:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        entries = list(self.entries or [])
        entries.sort(key=lambda e: int(e.number))

        with out.open("wb") as f:
            f.write(struct.pack("<i", int(self.header1)))
            f.write(struct.pack("<h", int(self.header2)))
            for e in entries:
                raw = (e.text or "").encode("utf-8", errors="replace")
                if len(raw) > 0x7FFF:
                    raise ValueError("cliloc entry text too long")
                f.write(struct.pack("<i", int(e.number)))
                f.write(struct.pack("<B", int(e.flag) & 0xFF))
                f.write(struct.pack("<h", len(raw)))
                f.write(raw)
