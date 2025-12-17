from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import Files
from uo_py_sdk.ultima.multis import Multis
from uo_py_sdk.ultima.multi_codec import MultiTileEntry, decode_multi_tiles, encode_multi_tiles


def test_multis_can_decode_some_entry() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    multis = Multis.from_files(files)

    entries = multis.file_index.load()

    decoded = None
    for i in range(min(2048, len(entries))):
        if not multis.file_index.valid(i, entries=entries):
            continue
        decoded = multis.multi_tiles(i)
        if decoded is not None and len(decoded[0]) > 0:
            break

    assert decoded is not None
    tiles, _use_new = decoded
    assert len(tiles) > 0


def test_multi_codec_roundtrip_old_and_new() -> None:
    tiles = [
        MultiTileEntry(item_id=0x1, offset_x=-1, offset_y=2, offset_z=0, flags=0),
        MultiTileEntry(item_id=0x4000, offset_x=3, offset_y=-4, offset_z=5, flags=0x7FFFFFFF),
    ]

    raw_old = encode_multi_tiles(tiles, use_new_format=False)
    decoded_old, use_new_old = decode_multi_tiles(raw_old)
    assert use_new_old is False
    assert decoded_old == [
        MultiTileEntry(item_id=0x1, offset_x=-1, offset_y=2, offset_z=0, flags=0),
        MultiTileEntry(item_id=0x4000, offset_x=3, offset_y=-4, offset_z=5, flags=0x7FFFFFFF),
    ]

    tiles_new = [
        MultiTileEntry(item_id=0x2, offset_x=0, offset_y=0, offset_z=0, flags=0x1_0000_0000),
    ]
    raw_new = encode_multi_tiles(tiles_new, use_new_format=True)
    decoded_new, use_new_new = decode_multi_tiles(raw_new)
    assert use_new_new is True
    assert decoded_new == tiles_new
