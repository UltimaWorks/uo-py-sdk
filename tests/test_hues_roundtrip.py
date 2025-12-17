from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima.hues import Hues


def test_hues_save_reload_roundtrip(tmp_path: Path) -> None:
    client_files = Path(__file__).parent / "client_files"
    original = Hues.from_path(client_files / "hues.mul")

    out_path = tmp_path / "hues_out.mul"
    original.save(out_path)

    reloaded = Hues.from_path(out_path)

    assert len(reloaded.hues) == 3000
    assert len(original.hues) == 3000

    # Compare semantic fields (we don't try to byte-compare the fixture file).
    for i in range(3000):
        a = original.hues[i]
        b = reloaded.hues[i]
        assert b.index == i
        assert a.colors == b.colors
        assert a.table_start == b.table_start
        assert a.table_end == b.table_end
        assert a.name == b.name
