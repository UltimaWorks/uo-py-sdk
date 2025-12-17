from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import Files, UOMap
from uo_py_sdk.ultima.map import BlockRect


def test_map_can_read_some_block() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    uomap = UOMap.from_files(files, map_id=0)

    # read a few blocks near origin
    block = uomap.read_block(0, 0)
    assert block is not None
    assert len(block.land) == 64

    # statics may be empty, but call must not crash
    assert isinstance(block.statics, list)

def test_map_iterators_respect_bounds() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = client_files

    # Build via Files facade (preferred entry point)
    from uo_py_sdk.ultima import Files

    m = UOMap.from_files(Files.from_path(files), 0)
    # tiny rect at origin should yield exactly 1 coordinate
    coords = list(m.iter_block_coords(BlockRect(0, 0, 0, 0)))
    assert coords == [(0, 0)]

    # out-of-range rect clamps
    coords2 = list(m.iter_block_coords(BlockRect(-10, -10, 0, 0)))
    assert coords2 == [(0, 0)]
