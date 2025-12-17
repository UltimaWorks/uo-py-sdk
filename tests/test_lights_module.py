from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import Files
from uo_py_sdk.ultima.lights import Lights


def test_lights_can_decode_some_entry() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    lights = Lights.from_files(files)

    entries = lights.file_index.load()

    decoded = None
    scan = min(2048, len(entries))
    for i in range(scan):
        if not lights.file_index.valid(i, entries=entries):
            continue
        decoded = lights.light_pixels_1555(i)
        if decoded is not None:
            break

    assert decoded is not None
    w, h, pixels = decoded
    assert w > 0 and h > 0
    assert len(pixels) == w * h
