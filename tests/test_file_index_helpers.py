from __future__ import annotations

import struct
from pathlib import Path

from uo_py_sdk.ultima.file_index import FileIndex, FileIndexIntegrityReport


def _write_idx(path: Path, *, entries: list[tuple[int, int, int]]) -> None:
    with path.open("wb") as f:
        for off, length, extra in entries:
            f.write(struct.pack("<iii", int(off), int(length), int(extra)))


def test_file_index_iter_valid_and_integrity(tmp_path: Path) -> None:
    # MUL has 16 bytes.
    mul = tmp_path / "foo.mul"
    mul.write_bytes(b"0123456789ABCDEF")

    idx = tmp_path / "fooidx.mul"
    # entry0: valid (offset 4, length 4)
    # entry1: empty
    # entry2: out of bounds (offset 14, length 4)
    _write_idx(idx, entries=[(4, 4, 0), (-1, -1, 0), (14, 4, 0)])

    fi = FileIndex(idx_path=idx, mul_path=mul, verdata=None, file_id=None)
    entries = fi.load()

    assert list(fi.iter_valid_indices(entries=entries)) == [0]
    assert fi.first_valid_index(entries=entries) == 0

    report = fi.scan_integrity(entries=entries)
    assert isinstance(report, FileIndexIntegrityReport)
    assert report.entry_count == 3
    assert report.valid_count == 1
    assert report.empty_count == 1
    assert report.mul_oob_count == 1
    assert report.invalid_count == 1


def test_file_index_open_reader_reads(tmp_path: Path) -> None:
    mul = tmp_path / "foo.mul"
    mul.write_bytes(b"abcdefgh")

    idx = tmp_path / "fooidx.mul"
    _write_idx(idx, entries=[(0, 4, 0), (4, 4, 0)])

    fi = FileIndex(idx_path=idx, mul_path=mul, verdata=None, file_id=None)
    snap = fi.snapshot()
    assert len(snap.entries) == 2

    with fi.open_reader(snapshot=snap) as r:
        assert r.read(0) == b"abcd"
        assert r.read(1) == b"efgh"
