from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mul.pair import MulPair
from .file_index import FileIndex
from .textures_codec import Texture, decode_texture_to_1555, encode_texture_from_1555


@dataclass(slots=True)
class Textures:
    """UltimaSDK-style access to texmaps/texidx textures."""

    file_index: FileIndex
    mul_pair: MulPair | None = None

    @classmethod
    def from_files(cls, files: "Files") -> "Textures":
        return cls(file_index=files.file_index("texmaps"), mul_pair=files.mul_pair("texmaps"))

    def read_texture_raw(self, index: int) -> tuple[bytes, int] | None:
        res = self.file_index.seek(index)
        if res is None:
            return None

        stream, length, extra, _patched = res
        try:
            data = stream.read(length)
        finally:
            stream.close()

        return data, extra

    def texture(self, index: int) -> Texture | None:
        rr = self.read_texture_raw(index)
        if rr is None:
            return None
        raw, extra = rr
        return decode_texture_to_1555(raw, extra=extra)

    def export_texture(self, index: int, out_path: str) -> bool:
        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for image export. Install Pillow or `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        tex = self.texture(index)
        if tex is None:
            return False

        img = Image.new("RGBA", (tex.size, tex.size))
        # We re-use the art codec PIL helper to keep color behavior identical.
        from .art_codec import pixels1555_to_pil_rgba

        img = pixels1555_to_pil_rgba(tex.size, tex.size, tex.pixels_1555)
        img.save(out_path)
        return True

    def _require_writable(self) -> MulPair:
        if self.mul_pair is None:
            raise RuntimeError(
                "This Textures instance was created read-only; use Textures.from_files(files) to enable writing."
            )
        return self.mul_pair

    def import_texture(self, index: int, image_path: str) -> None:
        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for image import. Install Pillow or `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        from .art_codec import pil_rgba_to_pixels1555

        img = Image.open(image_path)
        w, h, pixels = pil_rgba_to_pixels1555(img)
        if w != h or w not in (64, 128):
            raise ValueError("textures must be 64x64 or 128x128 pixels")

        payload, extra = encode_texture_from_1555(w, pixels)

        pair = self._require_writable()
        entries = pair.load_index() if pair.idx_path.exists() else []
        _, entries = pair.append_raw(payload, extra=extra, index=index, entries=entries)
        pair.save_index(entries)


if TYPE_CHECKING:
    from .files import Files
