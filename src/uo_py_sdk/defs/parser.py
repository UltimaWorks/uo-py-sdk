from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..errors import MulFormatError


@dataclass(frozen=True, slots=True)
class DefMapping:
    """Represents a simple `{type}.def` mapping.

    Many `.def` formats in the UO ecosystem are effectively `from -> to` (or to-list).
    This implementation stores `from -> list[int]`.
    """

    mapping: dict[int, list[int]]

    def resolve_first(self, index: int) -> int | None:
        values = self.mapping.get(index)
        return values[0] if values else None


def _strip_comments(line: str) -> str:
    for sep in ("#", "//"):
        if sep in line:
            line = line.split(sep, 1)[0]
    return line.strip()


def parse_def(text: str) -> DefMapping:
    """Parse a `.def` mapping file.

    Supported minimal forms:
    - `123 456`
    - `123 { 456 }`
    - `123 {456, 789}`

    Unknown lines are ignored rather than failing hard.
    """

    mapping: dict[int, list[int]] = {}

    for raw in text.splitlines():
        line = _strip_comments(raw)
        if not line:
            continue

        # Normalize braces and commas.
        line = line.replace("{", " { ").replace("}", " }")
        parts = [p for p in line.replace(",", " ").split() if p]
        if len(parts) < 2:
            continue

        try:
            src = int(parts[0])
        except ValueError:
            continue

        # Either `src dst` or `src { dst1 dst2 ... }`
        if parts[1] == "{":
            if "}" not in parts:
                continue
            try:
                end = parts.index("}")
                dsts = [int(p) for p in parts[2:end] if p not in ("{", "}")]
            except (ValueError, IndexError):
                continue
        else:
            try:
                dsts = [int(parts[1])]
            except ValueError:
                continue

        if dsts:
            mapping[src] = dsts

    return DefMapping(mapping=mapping)


def parse_def_file(path: str | Path) -> DefMapping:
    p = Path(path)
    if not p.exists():
        return DefMapping(mapping={})
    try:
        return parse_def(p.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        raise MulFormatError(str(e)) from e
