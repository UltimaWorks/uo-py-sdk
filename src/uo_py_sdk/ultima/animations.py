from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .animation_codec import AnimationFrame, decode_animation_record
from .file_index import FileIndex


@dataclass(slots=True)
class Animations:
    """UltimaSDK-style access to anim.mul/anim.idx (and anim2..anim6).

    This is a minimal read-only facade for decoding animation records into frames.

    Notes:
    - UO stores animations across multiple anim{N}.mul/idx subsets.
    - Index computation depends on body/action/direction and the file set.
    """

    file_index: FileIndex

    @classmethod
    def from_files(cls, files: "Files", *, file_set: int = 1) -> "Animations":
        if file_set == 1:
            asset = "anim"
        elif file_set in (2, 3, 4, 5, 6):
            asset = f"anim{int(file_set)}"
        else:
            raise ValueError("file_set must be 1..6")

        return cls(file_index=files.file_index(asset))

    @staticmethod
    def _compute_record_index(*, body: int, action: int, direction: int, file_set: int) -> tuple[int, bool]:
        """Compute IDX record index and whether to flip (direction > 4)."""

        body = int(body)
        action = int(action)
        direction = int(direction)
        file_set = int(file_set)

        if body < 0 or action < 0:
            return -1, False

        # Mirrors UltimaSDK GetFileIndex logic.
        if file_set == 1:
            if body < 200:
                index = body * 110
            elif body < 400:
                index = 22000 + ((body - 200) * 65)
            else:
                index = 35000 + ((body - 400) * 175)
        elif file_set == 2:
            if body < 200:
                index = body * 110
            else:
                index = 22000 + ((body - 200) * 65)
        elif file_set == 3:
            if body < 300:
                index = body * 65
            elif body < 400:
                index = 33000 + ((body - 300) * 110)
            else:
                index = 35000 + ((body - 400) * 175)
        elif file_set == 4:
            if body < 200:
                index = body * 110
            elif body < 400:
                index = 22000 + ((body - 200) * 65)
            else:
                index = 35000 + ((body - 400) * 175)
        elif file_set == 5:
            if (body < 200) and (body != 34):
                index = body * 110
            elif body < 400:
                index = 22000 + ((body - 200) * 65)
            else:
                index = 35000 + ((body - 400) * 175)
        elif file_set == 6:
            # UltimaSDK in this repo doesn’t include anim6, but most clients follow anim5 rules.
            if (body < 200) and (body != 34):
                index = body * 110
            elif body < 400:
                index = 22000 + ((body - 200) * 65)
            else:
                index = 35000 + ((body - 400) * 175)
        else:
            raise ValueError("file_set must be 1..6")

        index += action * 5
        if direction <= 4:
            index += direction
        else:
            index += direction - (direction - 4) * 2

        flip = direction > 4
        return int(index), bool(flip)

    def read_record_raw(self, *, body: int, action: int, direction: int, file_set: int = 1) -> bytes | None:
        index, _flip = self._compute_record_index(body=body, action=action, direction=direction, file_set=file_set)
        if index < 0:
            return None
        return self.file_index.read(index)

    def frames(self, *, body: int, action: int, direction: int, file_set: int = 1) -> list[AnimationFrame] | None:
        index, flip = self._compute_record_index(body=body, action=action, direction=direction, file_set=file_set)
        if index < 0:
            return None

        res = self.file_index.seek(index)
        if res is None:
            return None

        stream, length, _extra, _patched = res
        try:
            raw = stream.read(length)
        finally:
            stream.close()

        try:
            return decode_animation_record(raw, flip=flip)
        except Exception:
            return None

    def export_gif(
        self,
        *,
        body: int,
        action: int,
        direction: int,
        out_path: str | Path,
        file_set: int = 1,
        duration_ms: int = 100,
        loop: int = 0,
    ) -> bool:
        """Export an animation sequence to an animated GIF.

        Requires Pillow (install `uo-py-sdk[image]` or `uo-py-sdk[dev]`).

        Returns False when no decodable frames exist for the requested key.
        """

        try:
            from PIL import Image  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Pillow is required for GIF export. Install Pillow or `uo-py-sdk[image]` (or `uo-py-sdk[dev]`)."
            ) from e

        frames = self.frames(body=body, action=action, direction=direction, file_set=file_set)
        if not frames:
            return False

        from .art_codec import pixels1555_to_pil_rgba

        images: list[Image.Image] = []
        for fr in frames:
            if fr.width <= 0 or fr.height <= 0:
                continue
            if len(fr.pixels_1555) != (fr.width * fr.height):
                continue
            images.append(pixels1555_to_pil_rgba(fr.width, fr.height, fr.pixels_1555))

        if not images:
            return False

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        first, rest = images[0], images[1:]
        first.save(
            out,
            format="GIF",
            save_all=True,
            append_images=rest,
            duration=int(duration_ms),
            loop=int(loop),
        )
        return True


if TYPE_CHECKING:
    from .files import Files
