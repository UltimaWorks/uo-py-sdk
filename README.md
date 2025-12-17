# uo-py-sdk

Python-oriented Ultima Online client `{type}.mul`/`{type}idx.mul` content reader/writer framework.

## Goals

- Clean, typed, Pythonic APIs for reading/writing UO MUL containers
- Generic `{type}idx.mul` + `{type}.mul` container support (offset/length/extra)
- Pluggable “codecs” per asset type (art, gumps, sounds, texmaps, multi, etc.)
- Primarily a Python package for building other tools

## Naming convention

Most UO client data is stored as a pair:

- `{type}.mul` (data)
- `{type}idx.mul` (index)

Many asset types also have an optional `{type}.def` mapping file (e.g. `art.def`).

## Quickstart

```bash
python -m pip install -e .

# for local testing (tests + CustomTkinter example + PNG/JPG/BMP import/export)
python -m pip install -e .[dev]
python -m pytest
```

## Settings for tool authors (.env / env vars)

Tooling often wants defaults (client directory, output directory) without hardcoding.

This package includes `UoPySdkSettings`, which reads environment variables and can
optionally load a `.env` file when `python-dotenv` is installed.

See [.env.example](.env.example) for a template.

```python
from uo_py_sdk import UoPySdkSettings
from uo_py_sdk.ultima import Files

s = UoPySdkSettings.load()  # loads `.env` if python-dotenv is installed
files = Files.from_path(s.uo_dir) if s.uo_dir is not None else Files.from_path(r"C:\\Games\\Ultima Online")
```

Recognized env vars:

- `UO_DIR`: UO client directory
- `UO_OUTPUT_DIR`: default output directory (supports `{uo_dir}` placeholder)
- `UO_TEMP_DIR`: optional scratch directory

## Performance primitives (bulk reads)

When writing batch tools (export ranges, scan indices), it’s common to read thousands
of records. `FileIndex.snapshot()` caches parsed IDX entries + file sizes, and
`FileIndex.open_reader()` keeps underlying streams open for fast repeated reads.

```python
from uo_py_sdk.ultima import Files

files = Files.from_path(r"C:\\Games\\Ultima Online")
fi = files.file_index("art")
snap = fi.snapshot()

with fi.open_reader(snapshot=snap) as r:
    for i in fi.iter_valid_indices(entries=snap.entries, limit=1000):
        data = r.read(i)
        # ... process bytes ...
```

## GUI examples

See [examples/README.md](examples/README.md) for a CustomTkinter demo that browses `art.mul` and exports/imports images.

## Image import/export (art.mul)

The `Art` helper can export land/static art records to common image formats and import them back:

```python
from uo_py_sdk.ultima import Files, Art

files = Files.from_path(r"C:\\Games\\Ultima Online")
art = Art.from_files(files)

# export
art.export_land(0x000, "land_000.png")
art.export_static(0x0EED, "static_0EED.png")

# import (writes back into art.mul/artidx.mul)
art.import_land(0x000, "land_000.png")
art.import_static(0x0EED, "static_0EED.png")
```

## Status

This is an initial scaffold with core `{type}idx.mul` parsing and generic `{type}.mul` record IO.
