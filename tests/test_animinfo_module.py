from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima.animinfo import AnimInfo


def test_animinfo_mul_loads_fixture() -> None:
    client_files = Path(__file__).parent / "client_files"
    animinfo = AnimInfo.from_path(client_files / "animinfo.mul")

    assert len(animinfo.entries) == 1000
    assert animinfo.entries[0].unk1 == 516
    assert animinfo.entries[0].unk2 == 516
