from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import TileData


def test_tiledata_load_and_roundtrip(tmp_path: Path) -> None:
    client_files = Path(__file__).parent / "client_files"
    src = client_files / "tiledata.mul"

    td = TileData.from_path(src)

    assert len(td.land) == 0x4000
    assert len(td.land_headers) == 0x4000 // 32
    assert len(td.items) % 32 == 0
    assert len(td.item_headers) == len(td.items) // 32

    out = tmp_path / "tiledata.mul"
    td.save(out)

    assert out.read_bytes() == src.read_bytes()


def test_tiledata_csv_import_updates_one_entry(tmp_path: Path) -> None:
    # Keep this minimal: write 1-line CSV, import, verify in-memory update.
    client_files = Path(__file__).parent / "client_files"
    td = TileData.from_path(client_files / "tiledata.mul")

    # Land CSV: update tile 0 name/tex.
    land_csv = tmp_path / "land.csv"
    land_csv.write_text(
        "ID;Name;TextureID;HSAUnk1;Background;Weapon;Transparent;Translucent;Wall;Damage;Impassible;Wet;Unknow1;"
        "Surface;Bridge;Generic;Window;NoShoot;PrefixA;PrefixAn;Internal;Foliage;PartialHue;Unknow2;Map;"
        "Container/Height;Wearable;Lightsource;Animation;HoverOver;Unknow3;Armor;Roof;Door;StairBack;StairRight\n"
        "0x0000;my_land;0x0001;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0\n",
        encoding="cp1252",
    )
    td.import_land_csv(land_csv)
    assert td.land_tile(0).name == "my_land"
    assert (td.land_tile(0).tex_id & 0xFFFF) == 0x0001

    # Item CSV: update item 0 name/height.
    item_csv = tmp_path / "item.csv"
    item_csv.write_text(
        "ID;Name;Weight/Quantity;Layer/Quality;Gump/AnimID;Height;Hue;Class/Quantity;StackingOffset;MiscData;"
        "Unknown1;Unknown2;Unknown3;Background;Weapon;Transparent;Translucent;Wall;Damage;Impassible;Wet;Unknow1;"
        "Surface;Bridge;Generic;Window;NoShoot;PrefixA;PrefixAn;Internal;Foliage;PartialHue;Unknow2;Map;"
        "Container/Height;Wearable;Lightsource;Animation;HoverOver;Unknow3;Armor;Roof;Door;StairBack;StairRight\n"
        "0x0000;my_item;1;2;0x0000;7;0;0;0;0;0;0;0;"
        "0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0\n",
        encoding="cp1252",
    )
    td.import_item_csv(item_csv)
    assert td.item_tile(0).name == "my_item"
    assert td.item_tile(0).height == 7
