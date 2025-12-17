from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima.radarcol import RadarCol


def test_radarcol_loads_and_has_expected_size() -> None:
    client_files = Path(__file__).parent / "client_files"
    rc = RadarCol.from_path(client_files / "radarcol.mul")

    assert len(rc.colors) >= 0x8000

    # Basic accessors should not crash.
    _land = rc.get_land_color(0)
    _item = rc.get_item_color(0)
    assert isinstance(_land, int)
    assert isinstance(_item, int)
