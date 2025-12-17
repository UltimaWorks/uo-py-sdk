from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import Files
from uo_py_sdk.ultima.fonts import AsciiFonts, UnicodeFont, UnicodeFonts


def test_ascii_fonts_save_reload_roundtrip(tmp_path: Path) -> None:
    client_files = Path(__file__).parent / "client_files"
    original = AsciiFonts.from_path(client_files / "fonts.mul")

    out_path = tmp_path / "fonts_out.mul"
    original.save(out_path)

    reloaded = AsciiFonts.from_path(out_path)

    assert len(original.fonts) == 10
    assert len(reloaded.fonts) == 10

    for fi in range(10):
        a = original.fonts[fi]
        b = reloaded.fonts[fi]
        assert a.header == b.header
        assert len(a.glyphs) == 224
        assert len(b.glyphs) == 224
        for gi in range(224):
            ga = a.glyphs[gi]
            gb = b.glyphs[gi]
            assert (ga.width, ga.height, ga.unk) == (gb.width, gb.height, gb.unk)
            assert ga.pixels_1555 == gb.pixels_1555


def test_unicode_font_save_reload_roundtrip_for_renderable_glyphs(tmp_path: Path) -> None:
    client_files = Path(__file__).parent / "client_files"
    original = UnicodeFont.from_path(client_files / "unifont.mul")

    out_path = tmp_path / "unifont_out.mul"
    original.save(out_path)

    reloaded = UnicodeFont.from_path(out_path)

    # Only assert strict equality for glyphs that actually have bitmap data.
    for cp in range(0x10000):
        ga = original.glyph(cp)
        if ga.data is None or ga.width == 0 or ga.height == 0:
            continue
        gb = reloaded.glyph(cp)
        assert (ga.x_offset, ga.y_offset, ga.width, ga.height) == (gb.x_offset, gb.y_offset, gb.width, gb.height)
        assert gb.data == ga.data


def test_unicode_fonts_wrapper_save_writes_font0(tmp_path: Path) -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)

    fonts = UnicodeFonts.from_files(files)
    written = fonts.save(tmp_path)

    assert (tmp_path / "unifont.mul").exists()
    assert any(p.name.lower() == "unifont.mul" for p in written)
