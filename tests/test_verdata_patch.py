from __future__ import annotations

import struct
from pathlib import Path

from uo_py_sdk.ultima.file_index import FileIndex
from uo_py_sdk.ultima.verdata import Verdata


def _write_idx(path: Path, *, entries: list[tuple[int, int, int]]) -> None:
    # offset, length, extra (int32)
    with path.open("wb") as f:
        for off, length, extra in entries:
            f.write(struct.pack("<iii", off, length, extra))


def test_verdata_patch_read(tmp_path: Path) -> None:
    # Arrange a minimal UO dir with verdata.mul, dummy art.mul, and artidx.mul.
    uo_dir = tmp_path

    # Dummy mul (should NOT be used due to patch)
    (uo_dir / "art.mul").write_bytes(b"X" * 64)

    # artidx.mul with one empty record
    _write_idx(uo_dir / "artidx.mul", entries=[(-1, -1, 0)])

    payload = b"PATCHED!"
    count = 1
    table_size = 4 + 20 * count
    lookup = table_size

    # verdata.mul: [count][(file,index,lookup,length,extra)...][payload...]
    vd = bytearray()
    vd += struct.pack("<i", count)
    vd += struct.pack("<iiiii", 4, 0, lookup, len(payload), 123)  # file_id=4 (art.mul)
    vd += payload
    (uo_dir / "verdata.mul").write_bytes(vd)

    verdata = Verdata.from_uo_dir(uo_dir)
    fi = FileIndex(
        idx_path=uo_dir / "artidx.mul",
        mul_path=uo_dir / "art.mul",
        verdata=verdata,
        file_id=4,
    )

    # Act
    entries = fi.load()
    data = fi.read(0, entries=entries)

    # Assert
    assert data == payload
