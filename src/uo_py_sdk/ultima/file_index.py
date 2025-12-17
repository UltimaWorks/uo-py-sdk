from __future__ import annotations

from dataclasses import dataclass
from contextlib import AbstractContextManager
from pathlib import Path
from typing import BinaryIO, Iterable

from ..errors import MulFormatError
from ..mul.idx import IdxEntry, read_idx_entries
from .verdata import Verdata


@dataclass(frozen=True, slots=True)
class FileIndexIntegrityReport:
    entry_count: int
    valid_count: int
    invalid_count: int
    empty_count: int
    patched_count: int
    mul_missing_count: int
    mul_oob_count: int
    verdata_missing_count: int
    verdata_oob_count: int


@dataclass(frozen=True, slots=True)
class FileIndexSnapshot:
    """Cached, reusable view of a FileIndex.

    Tooling often wants to scan/read many records; repeatedly calling `load()` and
    `stat()` can dominate runtime on network drives or large installs.
    """

    entries: list[IdxEntry]
    mul_size: int | None
    verdata_size: int | None


class FileIndexReader(AbstractContextManager["FileIndexReader"]):
    """High-throughput reader for a FileIndex.

    Keeps MUL and/or VERDATA streams open and reuses a cached `entries` list.
    """

    def __init__(self, file_index: "FileIndex", *, snapshot: FileIndexSnapshot | None = None):
        self._fi = file_index
        self.snapshot = snapshot if snapshot is not None else file_index.snapshot()
        self._mul_fp: BinaryIO | None = None
        self._ver_fp: BinaryIO | None = None

    def __enter__(self) -> "FileIndexReader":
        if self._fi._mul_is_available():
            try:
                self._mul_fp = self._fi.mul_path.open("rb")
            except OSError:
                self._mul_fp = None
        if self._fi.verdata is not None and self._fi.verdata.path is not None:
            try:
                self._ver_fp = self._fi.verdata.open_stream()
            except OSError:
                self._ver_fp = None
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._mul_fp is not None:
                self._mul_fp.close()
        finally:
            self._mul_fp = None
        try:
            if self._ver_fp is not None:
                self._ver_fp.close()
        finally:
            self._ver_fp = None
        return False

    def read(self, index: int) -> bytes | None:
        return self._fi.read(index, entries=self.snapshot.entries, _mul_fp=self._mul_fp, _ver_fp=self._ver_fp)


@dataclass(slots=True)
class FileIndex:
    """UltimaSDK-style IDX/MUL accessor.

    This is a thin wrapper over `{type}idx.mul` + `{type}.mul`.

        Notes:
        - This implementation supports classic MUL/IDX and optional `verdata.mul` patching.
    """

    idx_path: Path
    mul_path: Path
    verdata: Verdata | None = None
    file_id: int | None = None

    def _mul_is_available(self) -> bool:
        try:
            return self.mul_path.exists() and self.mul_path.is_file()
        except OSError:
            return False

    def load(self) -> list[IdxEntry]:
        if not self.idx_path.exists():
            return []

        with self.idx_path.open("rb") as f:
            entries = read_idx_entries(f)

        # Apply verdata patches (UltimaSDK-style) if configured.
        if self.verdata is not None and self.file_id is not None and self.verdata.patches:
            for patch in self.verdata.patches:
                if patch.file_id != self.file_id:
                    continue
                if patch.index < 0 or patch.index >= len(entries):
                    continue
                entries[patch.index] = IdxEntry(
                    offset=patch.lookup,
                    length=int(patch.length) | 0x80000000,
                    extra=patch.extra,
                )

        return entries

    def snapshot(self) -> FileIndexSnapshot:
        entries = self.load()

        mul_size: int | None = None
        if self._mul_is_available():
            try:
                mul_size = self.mul_path.stat().st_size
            except OSError:
                mul_size = None

        verdata_size: int | None = None
        if self.verdata is not None and self.verdata.path is not None:
            try:
                verdata_size = self.verdata.path.stat().st_size
            except OSError:
                verdata_size = None

        return FileIndexSnapshot(entries=entries, mul_size=mul_size, verdata_size=verdata_size)

    def open_reader(self, *, snapshot: FileIndexSnapshot | None = None) -> FileIndexReader:
        """Open a high-throughput reader for bulk reads."""

        return FileIndexReader(self, snapshot=snapshot)

    def iter_valid_indices(
        self,
        *,
        entries: list[IdxEntry] | None = None,
        start: int = 0,
        end: int | None = None,
        limit: int | None = None,
    ) -> Iterable[int]:
        """Iterate indices that are valid and in-bounds.

        This is a convenience helper for tooling; it avoids re-loading the IDX
        file when `entries` is provided.
        """

        if entries is None:
            entries = self.load()

        start_i = max(0, int(start))
        end_i = len(entries) if end is None else min(len(entries), int(end))
        remaining = None if limit is None else max(0, int(limit))

        for i in range(start_i, end_i):
            if remaining is not None and remaining <= 0:
                break
            if self.valid(i, entries=entries):
                yield i
                if remaining is not None:
                    remaining -= 1

    def first_valid_index(self, *, entries: list[IdxEntry] | None = None, start: int = 0) -> int | None:
        """Return the first valid index at/after `start`, or None."""

        for i in self.iter_valid_indices(entries=entries, start=start, limit=1):
            return i
        return None

    def scan_integrity(self, *, entries: list[IdxEntry] | None = None) -> FileIndexIntegrityReport:
        """Compute a quick integrity summary for this IDX/MUL (+ optional verdata).

        Tooling frequently needs a fast, non-throwing overview:
        - how many entries exist
        - how many are empty
        - how many are valid
        - how many are out-of-bounds / missing backing files
        """

        if entries is None:
            entries = self.load()

        mul_size: int | None = None
        if self._mul_is_available():
            try:
                mul_size = self.mul_path.stat().st_size
            except OSError:
                mul_size = None

        ver_size: int | None = None
        ver_path = None if self.verdata is None else self.verdata.path
        if ver_path is not None:
            try:
                ver_size = ver_path.stat().st_size
            except OSError:
                ver_size = None

        valid_count = 0
        invalid_count = 0
        empty_count = 0
        patched_count = 0
        mul_missing_count = 0
        mul_oob_count = 0
        verdata_missing_count = 0
        verdata_oob_count = 0

        for e in entries:
            if e.is_empty:
                empty_count += 1
                continue

            length = e.decoded_length
            if length <= 0:
                invalid_count += 1
                continue

            if e.is_patched:
                patched_count += 1
                if ver_path is None or ver_size is None:
                    verdata_missing_count += 1
                    invalid_count += 1
                    continue
                if e.offset < 0 or (int(e.offset) + int(length)) > int(ver_size):
                    verdata_oob_count += 1
                    invalid_count += 1
                    continue
                valid_count += 1
                continue

            # Classic MUL
            if mul_size is None:
                mul_missing_count += 1
                invalid_count += 1
                continue
            if e.offset < 0 or (int(e.offset) + int(length)) > int(mul_size):
                mul_oob_count += 1
                invalid_count += 1
                continue
            valid_count += 1

        return FileIndexIntegrityReport(
            entry_count=len(entries),
            valid_count=valid_count,
            invalid_count=invalid_count,
            empty_count=empty_count,
            patched_count=patched_count,
            mul_missing_count=mul_missing_count,
            mul_oob_count=mul_oob_count,
            verdata_missing_count=verdata_missing_count,
            verdata_oob_count=verdata_oob_count,
        )

    @property
    def idx_length_bytes(self) -> int:
        try:
            return self.idx_path.stat().st_size
        except OSError:
            return 0

    @property
    def entry_count(self) -> int:
        # 12 bytes per entry
        return self.idx_length_bytes // 12

    def valid(self, index: int, *, entries: list[IdxEntry] | None = None, snapshot: FileIndexSnapshot | None = None) -> bool:
        if entries is None:
            if not self.idx_path.exists():
                return False
            if snapshot is not None:
                entries = snapshot.entries
            else:
                entries = self.load()

        if index < 0 or index >= len(entries):
            return False

        entry = entries[index]
        if entry.is_empty:
            return False

        length = entry.decoded_length
        if length <= 0:
            return False
        # Bounds checking (UltimaSDK-style): treat out-of-range records as invalid.
        if entry.is_patched:
            if entry.offset < 0:
                return False
            if self.verdata is None or self.verdata.path is None:
                return False
            try:
                size = snapshot.verdata_size if snapshot is not None else self.verdata.path.stat().st_size
            except OSError:
                return False
            return (entry.offset + length) <= size

        # Classic MUL is preferred when present.
        if self._mul_is_available():
            if entry.offset < 0:
                return False
            try:
                size = snapshot.mul_size if snapshot is not None else self.mul_path.stat().st_size
            except OSError:
                return False
            return (entry.offset + length) <= size

        return False

    def seek(self, index: int, *, entries: list[IdxEntry] | None = None) -> tuple[BinaryIO, int, int, bool] | None:
        """Open the MUL stream positioned at the record.

        Returns (stream, length, extra, patched). `patched` is always False
        in this initial implementation.

        Caller owns the returned stream and must close it.
        """

        if entries is None:
            entries = self.load()

        if index < 0 or index >= len(entries):
            return None

        entry = entries[index]
        if entry.is_empty:
            return None

        length = entry.decoded_length
        if length <= 0:
            return None
        if entry.is_patched:
            if self.verdata is None or self.verdata.path is None:
                return None
            if entry.offset < 0:
                return None
            try:
                if entry.offset + length > self.verdata.path.stat().st_size:
                    return None
            except OSError:
                return None
            stream = self.verdata.open_stream()
            stream.seek(entry.offset)
            return stream, length, entry.extra, True

        # Classic MUL
        if self._mul_is_available():
            try:
                if entry.offset + length > self.mul_path.stat().st_size:
                    return None
            except OSError:
                return None
            stream = self.mul_path.open("rb")
            stream.seek(entry.offset)
            return stream, length, entry.extra, False

        return None

    def read(
        self,
        index: int,
        *,
        entries: list[IdxEntry] | None = None,
        _mul_fp: BinaryIO | None = None,
        _ver_fp: BinaryIO | None = None,
    ) -> bytes | None:
        if entries is None:
            entries = self.load()

        if index < 0 or index >= len(entries):
            return None

        entry = entries[index]
        if entry.is_empty:
            return None

        length = entry.decoded_length
        if length <= 0:
            return None
        if entry.is_patched:
            if self.verdata is None or self.verdata.path is None:
                return None
            if entry.offset < 0:
                return None
            try:
                if entry.offset + length > self.verdata.path.stat().st_size:
                    return None
            except OSError:
                return None

            f = _ver_fp
            if f is None:
                with self.verdata.open_stream() as f2:
                    f2.seek(entry.offset)
                    return f2.read(length)
            f.seek(entry.offset)
            return f.read(length)

        # Classic MUL
        if self._mul_is_available():
            try:
                if entry.offset + length > self.mul_path.stat().st_size:
                    return None
            except OSError:
                return None

            f = _mul_fp
            if f is None:
                with self.mul_path.open("rb") as f2:
                    f2.seek(entry.offset)
                    return f2.read(length)
            f.seek(entry.offset)
            return f.read(length)

        return None
