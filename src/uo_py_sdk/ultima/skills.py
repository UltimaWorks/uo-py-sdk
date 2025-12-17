from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .file_index import FileIndex


@dataclass(frozen=True, slots=True)
class SkillInfo:
    index: int
    name: str
    is_action: bool
    extra: int


@dataclass(slots=True)
class Skills:
    """UltimaSDK-style access to skills.mul/skills.idx.

    Record payload:
    - 1 byte: bool is_action
    - N bytes: null-terminated name (Encoding.Default in UltimaSDK; we use cp1252)

    IDX extra is preserved as `extra`.
    """

    file_index: FileIndex

    @classmethod
    def from_files(cls, files: "Files") -> "Skills":
        return cls(file_index=files.file_index("skills"))

    def read_skill_raw(self, index: int) -> SkillInfo | None:
        res = self.file_index.seek(index)
        if res is None:
            return None

        stream, length, extra, _patched = res
        try:
            raw = stream.read(length)
        finally:
            stream.close()

        if not raw:
            return None

        is_action = bool(raw[0])
        name_bytes = raw[1:]
        if b"\x00" in name_bytes:
            name_bytes = name_bytes.split(b"\x00", 1)[0]

        # UltimaSDK uses Encoding.Default; on Windows this is usually cp1252.
        name = name_bytes.decode("cp1252", errors="replace")

        return SkillInfo(index=int(index), name=name, is_action=is_action, extra=int(extra))


if TYPE_CHECKING:
    from .files import Files
