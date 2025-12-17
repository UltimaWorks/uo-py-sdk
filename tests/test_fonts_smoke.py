from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import Files
from uo_py_sdk.ultima.fonts import (
    AsciiFonts,
    UnicodeFont,
    UnicodeFonts,
    find_first_renderable_ascii_glyph,
    find_first_renderable_unicode_glyph,
)


def test_ascii_fonts_load_and_have_some_glyph() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    fonts = AsciiFonts.from_files(files)

    assert len(fonts.fonts) == 10

    any_glyph = None
    for f in fonts.fonts:
        found = find_first_renderable_ascii_glyph(f)
        if found is not None:
            any_glyph = found
            break

    assert any_glyph is not None
    _idx, g = any_glyph
    assert g.width > 0 and g.height > 0
    assert len(g.pixels_1555) == g.width * g.height


def test_unicode_font_load_and_have_some_glyph() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    font = UnicodeFont.from_files(files, font_id=0)

    found = find_first_renderable_unicode_glyph(font, start=32)
    assert found is not None

    _cp, g = found
    assert g.width > 0 and g.height > 0
    assert g.data is not None
    assert len(g.pixels_1555()) == g.width * g.height


def test_unicode_fonts_wrapper_loads_font0() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)

    fonts = UnicodeFonts.from_files(files)
    assert len(fonts.fonts) == 13

    f0 = fonts.require(0)
    found = find_first_renderable_unicode_glyph(f0, start=32)
    assert found is not None
