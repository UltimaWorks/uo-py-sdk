from __future__ import annotations

import struct
from pathlib import Path

from uo_py_sdk.ultima import Files
from uo_py_sdk.ultima.skills import Skills


def _write_idx(path: Path, *, entries: list[tuple[int, int, int]]) -> None:
    # offset, length, extra (int32)
    with path.open("wb") as f:
        for off, length, extra in entries:
            f.write(struct.pack("<iii", off, length, extra))


def test_skills_can_read_minimal_record(tmp_path: Path) -> None:
    # Create a minimal isolated UO dir with skills.idx + skills.mul
    payload = b"\x01" + b"Alchemy\x00"  # is_action=True, name null-terminated
    (tmp_path / "skills.mul").write_bytes(payload)
    _write_idx(tmp_path / "skills.idx", entries=[(0, len(payload), 123)])

    files = Files.from_path(tmp_path)
    skills = Skills.from_files(files)

    s0 = skills.read_skill_raw(0)
    assert s0 is not None
    assert s0.index == 0
    assert s0.is_action is True
    assert s0.name == "Alchemy"
    assert s0.extra == 123
