from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..errors import MulFormatError
from ..mul.pair import MulPair
from .file_index import FileIndex
from .gump_codec import decode_gump_to_1555, encode_gump_from_1555


@dataclass(slots=True)
class Gumps:
    """UltimaSDK-style access to gumpart/gumpidx."""

    file_index: FileIndex
    mul_pair: MulPair | None = None

    @classmethod
    def from_files(cls, files: "Files") -> "Gumps":
        return cls(file_index=files.file_index("gump"), mul_pair=files.mul_pair("gump"))

    def read_gump_raw(self, index: int) -> tuple[bytes, int, int] | None:
        res = self.file_index.seek(index)
        if res is None:
            return None

        stream, length, extra, _patched = res
        try:
            data = stream.read(length)
        finally:
            stream.close()

        if extra == -1:
            return None

        width = (extra >> 16) & 0xFFFF
        height = extra & 0xFFFF
        if width <= 0 or height <= 0:
            return None

        # Guard against corrupt IDX extra values that would cause huge allocations.
        if (width * height) > 64_000_000:
            return None

        return data, width, height

    def gump_pixels_1555(self, index: int) -> tuple[int, int, list[int]] | None:
        rr = self.read_gump_raw(index)
        if rr is None:
            return None
        raw, width, height = rr
        try:
            pixels = decode_gump_to_1555(raw, width=width, height=height)
        except MulFormatError:
            return None
        return width, height, pixels

    def export_gump(self, index: int, out_path: str) -> bool:
        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for image export. Install Pillow or `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        decoded = self.gump_pixels_1555(index)
        if decoded is None:
            return False
        w, h, pixels = decoded

        from .art_codec import pixels1555_to_pil_rgba

        img = pixels1555_to_pil_rgba(w, h, pixels)
        img.save(out_path)
        return True

    def _require_writable(self) -> MulPair:
        if self.mul_pair is None:
            raise RuntimeError("This Gumps instance was created read-only; use Gumps.from_files(files) to enable writing.")
        return self.mul_pair

    def import_gump(self, index: int, image_path: str) -> None:
        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for image import. Install Pillow or `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        from .art_codec import pil_rgba_to_pixels1555

        img = Image.open(image_path)
        w, h, pixels = pil_rgba_to_pixels1555(img)

        payload = encode_gump_from_1555(w, h, pixels)
        extra = ((w & 0xFFFF) << 16) | (h & 0xFFFF)

        pair = self._require_writable()
        entries = pair.load_index() if pair.idx_path.exists() else []
        _, entries = pair.append_raw(payload, extra=extra, index=index, entries=entries)
        pair.save_index(entries)


if TYPE_CHECKING:
    from .files import Files
