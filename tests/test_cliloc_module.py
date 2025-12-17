from __future__ import annotations

import struct
from pathlib import Path

from uo_py_sdk.ultima.cliloc import CliLocFlag, Cliloc


def _write_cliloc(path: Path) -> None:
    # header1:int32, header2:int16
    # entry: number:int32, flag:u8, length:int16, utf8 bytes
    entries = [
        (1000, int(CliLocFlag.Original), "Hello"),
        (1001, int(CliLocFlag.Custom), "You see ~1_ITEM~."),
        (1002, int(CliLocFlag.Modified), "~1_NAME~ gives ~2_TARGET~ a hug"),
    ]

    buf = bytearray()
    buf += struct.pack("<ih", 123, 7)
    for number, flag, text in entries:
        raw = text.encode("utf-8")
        buf += struct.pack("<iBh", number, flag, len(raw))
        buf += raw

    path.write_bytes(buf)


def test_cliloc_parses_and_formats(tmp_path: Path) -> None:
    p = tmp_path / "cliloc.enu"
    _write_cliloc(p)

    cl = Cliloc.from_path(p, language="enu")
    assert cl.header1 == 123
    assert cl.header2 == 7

    assert cl.get_string(1000) == "Hello"

    e = cl.get_entry(1001)
    assert e is not None
    assert e.format("a sword") == "You see a sword."

    e2 = cl.get_entry(1002)
    assert e2 is not None
    assert e2.split_format("Alice\tBob") == "Alice gives Bob a hug"
