# Project Task List

This file tracks outstanding tasks and notes related to ongoing
development work.  Items are grouped loosely by priority and area of
concern.  Checkboxes (`[ ]` or `[x]`) indicate whether the task has
been completed.

## Preparatory work for UOP support

- [x] Introduce an `IAssetStore` interface that abstracts away the
  details of reading raw asset bytes.
- [x] Provide a default `MulIdxStore` implementation that uses the
  existing `FileIndex` class to read from legacy `.idx`/`.mul` files.
- [x] Add `ClientProfile` and `UltimaClient` classes to centralise
  client configuration and construct an asset store.  Expose these via
  `ultima.__init__` for convenient imports.
- [ ] Modify high level asset classes (e.g. `Art`, `Gumps`, `Sounds`)
  to optionally accept an `IAssetStore` and use it for reads instead of
  directly calling `FileIndex.read`.  Fall back to the existing
  behaviour when no store is provided to maintain backwards
  compatibility.
- [ ] Implement a `UopStore` that can read Mythic Package (`.uop`)
  archives and register it in `UltimaClient` based on the
  `prefer_uop` flag in the client profile.
- [ ] Extend the test suite with fixtures covering UOP archives and
  verify that the `UopStore` works transparently alongside legacy
  stores.

## General enhancements

- [ ] Add documentation examples demonstrating how to use
  `UltimaClient.open()` to load a client and export assets.
- [ ] Review and improve error handling across the SDK, ensuring
  meaningful exceptions are raised for corrupt or missing files.
- [ ] Incorporate a simple CLI tool for common tasks (exporting art,
  maps, etc.) as outlined in the high level roadmap.

Feel free to append additional tasks or notes as the project evolves.

## Performance and caching improvements

To make the SDK responsive for asset viewers and other interactive tools
without requiring every tool to reinvent caching logic, the following
work items should be addressed:

- [x] **Load all IDX entries into memory on startup.**  The SDK
  should populate and retain the index tables for each asset type in
  memory.  This avoids repeatedly parsing IDX files and allows callers
  to query record existence and size instantly.
- [x] **Implement an `MmapMulIdxStore` backend.**  This store should
  memory‑map the `.mul` files for each asset type using the built‑in
  `mmap` module and read bytes directly from the mapped region using
  the cached index entries.  Patched records (via `verdata.mul`) can
  fall back to the existing `FileIndex.read()` logic.
- [x] **Introduce a caching wrapper (`CachedAssetStore`).**  Wrap an
  inner `IAssetStore` and maintain a configurable LRU cache for raw
  record bytes.  The cache should evict entries when either the
  maximum number of entries or the maximum byte budget is exceeded.
- [ ] **Provide optional decoded‑image caching.**  For image assets,
  expose a helper or additional cache that stores decoded RGBA data or
  thumbnails, reducing repeated decode costs when the same asset is
  requested multiple times.
- [ ] **Add prefetch helpers.**  Implement simple background jobs
  (e.g. using `concurrent.futures.ThreadPoolExecutor`) to prefetch
  nearby records based on the current viewport in a UI, warming the
  caches ahead of user requests.
- [ ] **Document the recommended cache usage patterns.**  Update the
  SDK documentation and the `OVERVIEW.md` to explain how and why to
  enable memory mapping and caching for high‑performance viewers.