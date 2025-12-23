# UO Python SDK – Overview

This repository contains a Python SDK for accessing Ultima Online client
data files.  It is inspired by the classic UltimaSDK but reimagined
around idiomatic Python constructs and modern tooling.  The current
implementation provides read access to a wide range of asset types
(artwork, gumps, sounds, maps, multis, skills, etc.) from legacy
`.mul`/`.idx` pairs, along with optional write support for art
imports.  Verdata patch files are honoured transparently where
applicable.

## Project structure

```
src/uo_py_sdk/ultima/    # High level façade modules (Art, Gumps, Maps, etc.)
src/uo_py_sdk/mul/       # Low level IDX/MUL parsing and writing
src/uo_py_sdk/defs/      # DEF file parser and mapping helpers
src/uo_py_sdk/images/    # Colour conversion utilities
tests/                   # Unit tests covering core functionality
```

## Recent changes

The project has been extended with an **asset store** abstraction and a
convenience **client profile/entry point**:

- `ultima/asset_store.py` defines an `IAssetStore` interface and a
  `MulIdxStore` implementation.  This provides a single method
  `get_entry(asset_type, index)` which hides the details of reading
  legacy IDX/MUL files.  Introducing this seam is an important
  prerequisite for supporting additional formats such as Mythic Package
  (`.uop`) archives in the future.
- `ultima/client.py` defines `ClientProfile` and `UltimaClient` classes.
  `ClientProfile` captures configuration such as the client path and
  whether to prefer UOP archives.  `UltimaClient` wraps an existing
  `Files` instance, constructs an asset store and forwards per‑asset
  helpers.  This provides a single, stable entry point for tools to
  open a client installation without constructing multiple classes.
- `ultima/__init__.py` now exposes `ClientProfile`, `UltimaClient`,
  `IAssetStore` and `MulIdxStore` to consumers.

## Next steps

With the new abstractions in place, the SDK is ready for more advanced
features.  The most pressing work items are:

- Implement a `UopStore` that can read from Mythic Package (`.uop`)
  archives and register it with `UltimaClient` based on the
  `prefer_uop` flag in the profile.
- Update high level asset classes (e.g. `Art`, `Gumps`, `Sounds`) to
  optionally accept an `IAssetStore` and use it instead of directly
  calling `FileIndex`.  Existing behaviour should remain the default to
  preserve backwards compatibility.
- Extend the test harness with fixtures for UOP archives and write
  end‑to‑end tests covering the UOP store.

These enhancements will allow tools built on top of this SDK to work
with modern client installations without extracting legacy `.mul` files
by hand.