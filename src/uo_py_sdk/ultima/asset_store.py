"""Generic asset store abstractions.

This module introduces a minimal layer between the high level APIs and the
underlying client data files.  The intent is to make it easy to support
multiple backing formats (e.g. classic MUL/IDX pairs, Mythic Package
archives, test fixtures, etc.) without rewriting each asset class.  By
centralising the logic that maps an ``asset_type`` and ``index`` to a
binary payload, adding new storage backends becomes a matter of
implementing a single method.

At the time this module is introduced, the only supported backend is
``MulIdxStore`` which uses the existing :class:`~uo_py_sdk.ultima.file_index.FileIndex`
implementation to read records from classic IDX/MUL pairs.  Future work
will add a UOP-backed store that plugs into the same interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional

from .files import Files


class IAssetStore(ABC):
    """Abstract base class for client asset stores.

    An asset store knows how to locate and return the raw bytes for a
    particular asset type (e.g. ``"art"``) and index (e.g. an item or land
    tile ID).  The details of how those bytes are obtained – whether via
    MUL/IDX pairs, UOP archives, verdata patching or some other mechanism –
    are hidden behind this interface.
    """

    @abstractmethod
    def get_entry(self, asset_type: str, index: int) -> Optional[bytes]:
        """Return the raw record bytes for ``asset_type`` at ``index``.

        A return value of ``None`` indicates that the requested entry was
        not found or could not be read.  Implementations should **not**
        raise exceptions for missing entries – consumers expect a ``None``
        return for out-of-range indices or empty slots.

        Parameters
        ----------
        asset_type: str
            The logical asset type (e.g. ``"art"``, ``"gumpart"``,
            ``"sound"``, etc.).  The name should match those used by
            :mod:`uo_py_sdk.ultima.files`.
        index: int
            The zero‑based record index.

        Returns
        -------
        Optional[bytes]
            The raw bytes of the entry, or ``None`` if the entry is
            unavailable.
        """
        raise NotImplementedError


class MulIdxStore(IAssetStore):
    """Classic IDX/MUL backed asset store.

    This store uses the existing :class:`~uo_py_sdk.ultima.file_index.FileIndex`
    implementation to read entries from ``.idx``/``.mul`` file pairs.
    Instances of this class are cheap to construct and cache file index
    instances for each asset type on first use.
    """

    def __init__(self, files: Files) -> None:
        self._files: Files = files
        self._file_indices: Dict[str, object] = {}

    def _get_file_index(self, asset_type: str):
        # Delay import to avoid circular dependency issues.  FileIndex is
        # available from uo_py_sdk.ultima.file_index.
        from .file_index import FileIndex  # noqa: F401  # imported for type checkers

        fi = self._file_indices.get(asset_type)
        if fi is None:
            fi = self._files.file_index(asset_type)
            # Only cache if it really is a FileIndex instance.  If
            # ``files.file_index`` returns ``None`` (e.g. missing files), we
            # still store the ``None`` sentinel to avoid repeated lookups.
            self._file_indices[asset_type] = fi
        return fi

    def get_entry(self, asset_type: str, index: int) -> Optional[bytes]:
        fi = self._get_file_index(asset_type)
        if fi is None:
            return None
        # The read method tolerates out-of-range indices and returns None.
        try:
            return fi.read(index)  # type: ignore[no-any-return]
        except Exception:
            # Reading can fail for a variety of reasons (corrupt files,
            # permissions, etc.).  To preserve the non‑throwing contract,
            # swallow the error and return None.
            return None


class MmapMulIdxStore(IAssetStore):
    """Memory‑mapped MUL/IDX asset store.

    This implementation accelerates repeated reads by memory‑mapping the
    underlying `.mul` files and caching IDX entries in memory.  It uses
    :class:`uo_py_sdk.ultima.file_index.FileIndex` to obtain patched IDX
    entries and falls back to ``FileIndex.read()`` for records flagged
    with the high bit (typically indicating a verdata patch).  For all
    other records, bytes are sliced directly from the memory‑mapped
    backing file.  The class maintains one memory map per asset type and
    closes file handles only when the store instance is garbage
    collected.
    """

    def __init__(self, files: Files) -> None:
        self._files = files
        self._file_indices: Dict[str, object] = {}
        # Cache of idx entry lists per asset_type.  None indicates
        # missing files.
        self._entries: Dict[str, Optional[list]] = {}
        # Map of asset_type to (file object, mmap object).  None means
        # mapping failed.
        self._mm: Dict[str, Optional[tuple]] = {}

    def _get_file_index(self, asset_type: str):
        # Reuse the same helper as MulIdxStore to fetch or memoize the
        # FileIndex instance.


        fi = self._file_indices.get(asset_type)
        if fi is None:
            fi = self._files.file_index(asset_type)
            self._file_indices[asset_type] = fi
        return fi

    def _get_entries(self, asset_type: str):
        # Load and patch the IDX entries once per asset type.
        if asset_type not in self._entries:
            fi = self._get_file_index(asset_type)
            if fi is None:
                self._entries[asset_type] = None
            else:
                try:
                    entries = fi.load()
                except Exception:
                    entries = None
                self._entries[asset_type] = entries
        return self._entries.get(asset_type)

    def _get_mmap(self, asset_type: str):
        # Create or return an existing memory map for the MUL file.
        import mmap

        if asset_type in self._mm:
            return self._mm[asset_type]
        fi = self._get_file_index(asset_type)
        if fi is None:
            self._mm[asset_type] = None
            return None
        # If the MUL path is unavailable, we cannot mmap.
        try:
            mul_path = fi.mul_path
        except Exception:
            self._mm[asset_type] = None
            return None
        try:
            # Open file and create mmap
            fp = mul_path.open("rb")  # type: ignore[call-arg]
            mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
            self._mm[asset_type] = (fp, mm)
            return self._mm[asset_type]
        except Exception:
            # Unable to memory‑map; record sentinel
            self._mm[asset_type] = None
            return None

    def get_entry(self, asset_type: str, index: int) -> Optional[bytes]:
        entries = self._get_entries(asset_type)
        if not entries:
            return None
        # Index bounds check
        if index < 0 or index >= len(entries):
            return None
        entry = entries[index]
        # Each IdxEntry has offset and length attributes.  A length <= 0
        # implies an empty or invalid record.  A high bit set on length
        # indicates that the entry should be read via FileIndex.read(),
        # usually because the record is patched in verdata.mul.
        length = entry.length  # type: ignore[attr-defined]
        if length <= 0:
            return None
        # Mask out the high bit to get the actual length.
        payload_length = length & 0x7FFFFFFF
        # If the high bit is set, fall back to FileIndex.read().  This
        # covers verdata patches and other special cases.
        if (length & 0x80000000) != 0:
            fi = self._get_file_index(asset_type)
            if fi is None:
                return None
            try:
                return fi.read(index)  # type: ignore[no-any-return]
            except Exception:
                return None
        # Otherwise, read from the memory map.
        mm_tuple = self._get_mmap(asset_type)
        if mm_tuple is None:
            # As a fallback, delegate to FileIndex.read().
            fi = self._get_file_index(asset_type)
            if fi is None:
                return None
            try:
                return fi.read(index)  # type: ignore[no-any-return]
            except Exception:
                return None
        fp, mm = mm_tuple
        offset = entry.offset  # type: ignore[attr-defined]
        try:
            return mm[offset : offset + payload_length]
        except Exception:
            return None


class CachedAssetStore(IAssetStore):
    """LRU‑cached wrapper around another asset store.

    This store decorates an inner :class:`IAssetStore` and caches raw
    record bytes in a least‑recently‑used (LRU) cache with a bounded
    number of entries and/or a maximum total byte size.  When either
    limit is exceeded, the least‑recently used items are evicted.  The
    cache is keyed by ``(asset_type, index)`` tuples.  Missing or
    ``None`` records are not cached.
    """

    def __init__(self, inner: IAssetStore, *, max_entries: int = 1024, max_bytes: int = 256 * 1024 * 1024) -> None:
        self.inner = inner
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        # OrderedDict for LRU behaviour: newest at end
        from collections import OrderedDict

        self._cache: "OrderedDict[tuple, bytes]" = OrderedDict()
        self._current_bytes: int = 0

    def _evict(self):
        # Evict entries until both limits are satisfied
        while self._cache and (len(self._cache) > self.max_entries or self._current_bytes > self.max_bytes):
            key, value = self._cache.popitem(last=False)
            self._current_bytes -= len(value)

    def get_entry(self, asset_type: str, index: int) -> Optional[bytes]:
        key = (asset_type, index)
        try:
            # Fast path: return cached value and move it to the end
            value = self._cache.pop(key)  # type: ignore[index]
            self._cache[key] = value
            return value
        except KeyError:
            pass
        # Miss: delegate to inner store
        raw = self.inner.get_entry(asset_type, index)
        if raw is None:
            return None
        # Cache the result
        self._cache[key] = raw
        self._current_bytes += len(raw)
        # Evict if necessary
        self._evict()
        return raw