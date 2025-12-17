from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import Files, UOMap


def test_export_block_image(tmp_path: Path) -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    uomap = UOMap.from_files(files, map_id=0)

    out = tmp_path / "block_0_0.png"
    ok = uomap.export_block_image(0, 0, str(out))
    assert ok is True
    assert out.exists()
    assert out.stat().st_size > 0
