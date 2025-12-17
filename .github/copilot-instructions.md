# Copilot instructions (uo-py-sdk)

## Repo purpose + structure
- This is a typed Python 3.10+ library for reading/writing Ultima Online client assets stored in `{type}.mul` + `{type}idx.mul` pairs (see [src/uo_py_sdk](../src/uo_py_sdk)).
- High-level façade modules live in [src/uo_py_sdk/ultima](../src/uo_py_sdk/ultima) (UltimaSDK-inspired API surface).
- Low-level, format-focused helpers live in:
  - [src/uo_py_sdk/mul](../src/uo_py_sdk/mul) for generic IDX/MUL operations
  - [src/uo_py_sdk/defs](../src/uo_py_sdk/defs) for `{type}.def` mapping parsing
  - [src/uo_py_sdk/paths.py](../src/uo_py_sdk/paths.py) for resolving client filenames (with special-case overrides)
- The [Ultima](../Ultima) C# directory is a reference for expected behavior; the Python code is an original implementation.

## Key APIs (start here)
- Client root resolver: `uo_py_sdk.ultima.Files.from_path(uo_dir)` in [src/uo_py_sdk/ultima/files.py](../src/uo_py_sdk/ultima/files.py)
  - Provides `file_index(asset_type)` (read with optional `verdata.mul` patching) and `mul_pair(asset_type)` (raw read/write).
- Asset helpers follow the same pattern:
  - Art: `uo_py_sdk.ultima.Art.from_files(files)` in [src/uo_py_sdk/ultima/art.py](../src/uo_py_sdk/ultima/art.py)
  - Gumps: `uo_py_sdk.ultima.Gumps.from_files(files)` in [src/uo_py_sdk/ultima/gumps.py](../src/uo_py_sdk/ultima/gumps.py)
  - Multis: `uo_py_sdk.ultima.Multis.from_files(files)` in [src/uo_py_sdk/ultima/multis.py](../src/uo_py_sdk/ultima/multis.py)
  - Sounds: `uo_py_sdk.ultima.Sounds.from_files(files)` in [src/uo_py_sdk/ultima/sounds.py](../src/uo_py_sdk/ultima/sounds.py)
  - Textures: `uo_py_sdk.ultima.Textures.from_files(files)` in [src/uo_py_sdk/ultima/textures.py](../src/uo_py_sdk/ultima/textures.py)
  - TileData is a single-file loader (`tiledata.mul`), not an IDX/MUL pair: [src/uo_py_sdk/ultima/tiledata.py](../src/uo_py_sdk/ultima/tiledata.py)
  - Hues is a single-file loader (`hues.mul`), not an IDX/MUL pair: [src/uo_py_sdk/ultima/hues.py](../src/uo_py_sdk/ultima/hues.py)

## Important conventions (easy to miss)
- `asset_type` names are user-facing keys (e.g. `"art"`, `"gump"`, `"texmaps"`). Some have non-standard historical filenames:
  - Overrides are in `MulPairPaths._PAIR_OVERRIDES` ([src/uo_py_sdk/paths.py](../src/uo_py_sdk/paths.py)). Example: `"gump"` maps to `gumpart.mul` + `gumpidx.mul` + optional `gump.def`.
  - Another common override: `"multi"` maps to `multi.mul` + `multi.idx`.
- Paths are resolved case-insensitively when needed (Windows-like client installs) via `_resolve_existing_case_insensitive`.
- IDX semantics:
  - Each entry is `<int32 offset, int32 length, int32 extra>` (12 bytes), see [src/uo_py_sdk/mul/idx.py](../src/uo_py_sdk/mul/idx.py).
  - Unused entries are typically `-1/-1/0` (or `-1/-1/-1`).
  - The high bit of `length` indicates a `verdata.mul` patch (UltimaSDK convention). `IdxEntry.decoded_length` masks it off.
- `FileIndex` applies `verdata.mul` patches when `verdata` + `file_id` are provided (see [src/uo_py_sdk/ultima/file_index.py](../src/uo_py_sdk/ultima/file_index.py)).

## Read vs write behavior
- Read flows are generally: `entries = file_index.load()` then `file_index.valid(i, entries=entries)` / `file_index.read(i, entries=entries)`.
- Write flows use `MulPair.append_raw(...)` (see [src/uo_py_sdk/mul/pair.py](../src/uo_py_sdk/mul/pair.py)):
  - Writes are append-only: new payload bytes are appended to `{type}.mul` and the IDX entry is updated to point at the new offset.
  - Asset import helpers (`Art.import_*`, `Gumps.import_gump`, `Textures.import_texture`) follow this pattern.
- Image import/export requires Pillow (install via `uo-py-sdk[image]` or `uo-py-sdk[dev]` per [pyproject.toml](../pyproject.toml)).

## Dev workflows (commands that match this repo)
- Install:
  - `python -m pip install -e .`
  - `python -m pip install -e .[image]` (Pillow only; enables image import/export helpers)
  - `python -m pip install -e .[dev]` (pytest + Pillow + CustomTkinter)
- Run tests (configured as `-q` in [pyproject.toml](../pyproject.toml)):
  - `python -m pytest`
- Examples:
  - `python examples/ctk_art_browser.py`

## Tests + fixtures
- Tests use binary fixtures under [tests/client_files](../tests/client_files); avoid modifying these files in-place.
- Good reference tests when changing core behavior:
  - IDX parsing/writing: [tests/test_idx_roundtrip.py](../tests/test_idx_roundtrip.py)
  - Verdata patching: [tests/test_verdata_patch.py](../tests/test_verdata_patch.py)
  - Codec roundtrips: [tests/test_art_codec_roundtrip.py](../tests/test_art_codec_roundtrip.py)
  - Smoke usage of `Files` + asset modules: [tests/test_ultima_modules_smoke.py](../tests/test_ultima_modules_smoke.py)

## Error model
- Prefer raising `MulFormatError` for malformed inputs and `MulIndexOutOfRange` for bounds issues (see [src/uo_py_sdk/errors.py](../src/uo_py_sdk/errors.py)).
- DEF parsing is intentionally forgiving: unknown lines are ignored rather than failing hard (see [src/uo_py_sdk/defs/parser.py](../src/uo_py_sdk/defs/parser.py)).

## Roadmap
- Local-only (typically untracked) roadmap/notes: [.venv/ROADMAP_TODO.md](../.venv/ROADMAP_TODO.md)
