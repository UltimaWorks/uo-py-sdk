from __future__ import annotations

import io

from uo_py_sdk.mul.idx import IdxEntry, read_idx_entries, write_idx_entries


def test_idx_roundtrip() -> None:
    entries = [
        IdxEntry(0, 10, 3),
        IdxEntry(-1, -1, 0),
        IdxEntry(1234, 56, 0),
    ]

    buf = io.BytesIO()
    write_idx_entries(buf, entries)

    buf.seek(0)
    loaded = read_idx_entries(buf)

    assert loaded == entries
