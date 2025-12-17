from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .file_index import FileIndex
from ..mul.pair import MulPair
from .art_codec import (
    decode_land_to_1555,
    decode_static_to_1555,
    encode_land_from_1555,
    encode_static_from_1555,
    pil_rgba_to_pixels1555,
    pixels1555_to_pil_rgba,
)


@dataclass(slots=True)
class Art:
    """UltimaSDK-style access to `art.mul`/`artidx.mul`.

    This module currently exposes raw record bytes for land/static art.
    (Bitmap decoding/encoding can be layered on later.)
    """

    file_index: FileIndex
    mul_pair: MulPair | None = None

    @classmethod
    def from_files(cls, files: "Files") -> "Art":
        return cls(file_index=files.file_index("art"), mul_pair=files.mul_pair("art"))

    def get_idx_length(self) -> int:
        return self.file_index.entry_count

    def get_max_item_id(self) -> int:
        # Mirrors the common UltimaSDK heuristic.
        count = self.get_idx_length()
        if count >= 0x13FDC:
            return 0xFFFF
        if count == 0xC000:
            return 0x7FFF
        return 0x3FFF

    def get_legal_item_id(self, item_id: int, *, check_max_id: bool = True) -> int:
        if item_id < 0:
            return 0
        if check_max_id and item_id > self.get_max_item_id():
            return 0
        return int(item_id)

    def read_land_raw(self, land_id: int) -> bytes | None:
        land_id = land_id & 0x3FFF
        return self.file_index.read(land_id)

    def read_static_raw(self, item_id: int) -> bytes | None:
        item_id = self.get_legal_item_id(item_id)
        return self.file_index.read(item_id + 0x4000)

    # Image export

    def land_image(self, land_id: int):
        raw = self.read_land_raw(land_id)
        if raw is None:
            return None
        pixels = decode_land_to_1555(raw)
        return pixels1555_to_pil_rgba(44, 44, pixels)

    def static_image(self, item_id: int, *, check_max_id: bool = True):
        raw = self.read_static_raw(item_id) if check_max_id else self.file_index.read(item_id + 0x4000)
        if raw is None:
            return None
        decoded = decode_static_to_1555(raw)
        return pixels1555_to_pil_rgba(decoded.width, decoded.height, decoded.pixels_1555)

    def export_land(self, land_id: int, out_path: str) -> bool:
        img = self.land_image(land_id)
        if img is None:
            return False
        img.save(out_path)
        return True

    def export_static(self, item_id: int, out_path: str, *, check_max_id: bool = True) -> bool:
        img = self.static_image(item_id, check_max_id=check_max_id)
        if img is None:
            return False
        img.save(out_path)
        return True

    # Image import + write-back

    def _require_writable(self) -> MulPair:
        if self.mul_pair is None:
            raise RuntimeError("This Art instance was created read-only; use Art.from_files(files) to enable writing.")
        return self.mul_pair

    def import_land(self, land_id: int, image_path: str) -> None:
        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for image import. Install Pillow or `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        img = Image.open(image_path)
        w, h, pixels = pil_rgba_to_pixels1555(img)
        if (w, h) != (44, 44):
            raise ValueError("land tiles must be exactly 44x44 pixels")

        payload = encode_land_from_1555(pixels)
        pair = self._require_writable()
        entries = pair.load_index() if pair.idx_path.exists() else []
        _, entries = pair.append_raw(payload, index=(land_id & 0x3FFF), entries=entries)
        pair.save_index(entries)

    def import_static(self, item_id: int, image_path: str, *, check_max_id: bool = True) -> None:
        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for image import. Install Pillow or `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        if check_max_id:
            item_id = self.get_legal_item_id(item_id)

        img = Image.open(image_path)
        w, h, pixels = pil_rgba_to_pixels1555(img)
        payload = encode_static_from_1555(w, h, pixels)

        pair = self._require_writable()
        entries = pair.load_index() if pair.idx_path.exists() else []
        _, entries = pair.append_raw(payload, index=(item_id + 0x4000), entries=entries)
        pair.save_index(entries)


if TYPE_CHECKING:
    from .files import Files
