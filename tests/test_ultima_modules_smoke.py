from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import Files
from uo_py_sdk.ultima.gumps import Gumps
from uo_py_sdk.ultima.hues import Hues
from uo_py_sdk.ultima.textures import Textures


def test_hues_mul_loads() -> None:
    client_files = Path(__file__).parent / "client_files"
    hues = Hues.from_path(client_files / "hues.mul")
    assert len(hues.hues) == 3000
    assert hues.get_hue(0).index == 0


def test_gumps_can_decode_some_entry() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    gumps = Gumps.from_files(files)

    entries = gumps.file_index.load()

    decoded = None
    for i, e in enumerate(entries[:2048]):
        if not gumps.file_index.valid(i, entries=entries) or e.extra == -1:
            continue
        decoded = gumps.gump_pixels_1555(i)
        if decoded is not None:
            break

    assert decoded is not None
    w, h, pixels = decoded
    assert w > 0 and h > 0
    assert len(pixels) == w * h


def test_textures_can_decode_some_entry() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    textures = Textures.from_files(files)

    entries = textures.file_index.load()
    index = None
    for i, e in enumerate(entries[:2048]):
        if textures.file_index.valid(i, entries=entries):
            index = i
            break

    assert index is not None
    tex = textures.texture(index)
    assert tex is not None
    assert tex.size in (64, 128)
    assert len(tex.pixels_1555) == tex.size * tex.size
