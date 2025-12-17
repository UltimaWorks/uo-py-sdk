from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from ..mul.pair import MulPair
from .file_index import FileIndex
from .multi_codec import (
    MultiTileEntry,
    decode_multi_tiles,
    encode_multi_tiles,
    format_multi_txt,
    format_multi_uoa,
    format_multi_wsc,
    parse_multi_txt,
    parse_multi_uoa,
    parse_multi_wsc,
)


@dataclass(slots=True)
class Multis:
    """UltimaSDK-style access to multi.mul/multi.idx.

    A multi record is a list of components:
    - item_id: u16 (static art id)
    - offsets: x,y,z (i16)
    - flags: u32 (classic) or u64 (Post-HS)

    Text import/export formats mirror UltimaSDK:
    - TXT (0xITEM X Y Z FLAGS)
    - WSC
    - UOA
    """

    file_index: FileIndex
    mul_pair: MulPair | None = None

    @classmethod
    def from_files(cls, files: "Files") -> "Multis":
        return cls(file_index=files.file_index("multi"), mul_pair=files.mul_pair("multi"))

    def _require_writable(self) -> MulPair:
        if self.mul_pair is None:
            raise RuntimeError(
                "This Multis instance was created read-only; use Multis.from_files(files) to enable writing."
            )
        return self.mul_pair

    def read_multi_raw(self, index: int) -> bytes | None:
        res = self.file_index.seek(index)
        if res is None:
            return None

        stream, length, _extra, _patched = res
        try:
            return stream.read(length)
        finally:
            stream.close()

    def multi_tiles(self, index: int) -> tuple[list[MultiTileEntry], bool] | None:
        raw = self.read_multi_raw(index)
        if raw is None:
            return None
        try:
            tiles, use_new = decode_multi_tiles(raw)
        except Exception:
            return None
        return tiles, use_new

    # Export

    def export_txt(self, index: int, out_path: str | Path) -> bool:
        decoded = self.multi_tiles(index)
        if decoded is None:
            return False
        tiles, _use_new = decoded
        Path(out_path).write_text(format_multi_txt(tiles), encoding="cp1252", errors="replace")
        return True

    def export_wsc(self, index: int, out_path: str | Path) -> bool:
        decoded = self.multi_tiles(index)
        if decoded is None:
            return False
        tiles, _use_new = decoded
        Path(out_path).write_text(format_multi_wsc(tiles), encoding="cp1252", errors="replace")
        return True

    def export_uoa(self, index: int, out_path: str | Path) -> bool:
        decoded = self.multi_tiles(index)
        if decoded is None:
            return False
        tiles, _use_new = decoded
        Path(out_path).write_text(format_multi_uoa(tiles), encoding="cp1252", errors="replace")
        return True

    # Import + write-back

    def import_tiles(self, index: int, tiles: Iterable[MultiTileEntry], *, use_new_format: bool | None = None) -> None:
        tile_list = list(tiles)
        if use_new_format is None:
            use_new_format = any(int(t.flags) > 0xFFFFFFFF for t in tile_list)

        payload = encode_multi_tiles(tile_list, use_new_format=bool(use_new_format))

        pair = self._require_writable()
        entries = pair.load_index() if pair.idx_path.exists() else []
        _, entries = pair.append_raw(payload, index=int(index), entries=entries)
        pair.save_index(entries)

    def import_txt(self, index: int, txt_path: str | Path, *, use_new_format: bool | None = None) -> None:
        text = Path(txt_path).read_text(encoding="cp1252", errors="replace")
        tiles = parse_multi_txt(text)
        self.import_tiles(index, tiles, use_new_format=use_new_format)

    def import_uoa(self, index: int, uoa_path: str | Path, *, use_new_format: bool | None = None) -> None:
        text = Path(uoa_path).read_text(encoding="cp1252", errors="replace")
        tiles = parse_multi_uoa(text)
        self.import_tiles(index, tiles, use_new_format=use_new_format)

    def import_wsc(self, index: int, wsc_path: str | Path, *, use_new_format: bool | None = None) -> None:
        text = Path(wsc_path).read_text(encoding="cp1252", errors="replace")
        tiles = parse_multi_wsc(text)
        self.import_tiles(index, tiles, use_new_format=use_new_format)


if TYPE_CHECKING:
    from .files import Files
