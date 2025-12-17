from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..defs.parser import DefMapping
from ..mul.pair import MulPair
from .file_index import FileIndex
from .sound_codec import SoundPcm, build_sound_record, parse_sound_record, read_wav_pcm_s16le, write_wav_pcm_s16le


@dataclass(slots=True)
class Sounds:
    """UltimaSDK-style access to sound.mul/soundidx.mul.

    Record format (classic MUL):
    - 32 byte ASCII name (null padded)
    - followed by 16-bit PCM mono @ 22050 Hz (s16le)

    If `sound.def` exists, missing entries may be translated via its mapping.
    """

    file_index: FileIndex
    mul_pair: MulPair | None = None
    def_mapping: DefMapping | None = None

    @classmethod
    def from_files(cls, files: "Files") -> "Sounds":
        return cls(
            file_index=files.file_index("sound"),
            mul_pair=files.mul_pair("sound"),
            def_mapping=files.def_mapping("sound"),
        )

    def _require_writable(self) -> MulPair:
        if self.mul_pair is None:
            raise RuntimeError(
                "This Sounds instance was created read-only; use Sounds.from_files(files) to enable writing."
            )
        return self.mul_pair

    def resolve_sound_index(
        self, sound_id: int, *, entries: list | None = None
    ) -> tuple[int, bool] | None:
        """Resolve a sound id to an actual record index.

        Returns `(actual_index, translated)` or None if not resolvable.
        """

        if sound_id < 0:
            return None

        if entries is None:
            entries = self.file_index.load()

        if self.file_index.valid(sound_id, entries=entries):
            return int(sound_id), False

        mapping = self.def_mapping
        if mapping is None:
            return None

        alt = mapping.resolve_first(int(sound_id))
        if alt is None:
            return None

        if self.file_index.valid(alt, entries=entries):
            return int(alt), True

        return None

    def read_sound_raw(self, sound_id: int, *, entries: list | None = None) -> SoundPcm | None:
        resolved = self.resolve_sound_index(sound_id, entries=entries)
        if resolved is None:
            return None
        actual, _translated = resolved

        res = self.file_index.seek(actual, entries=entries)
        if res is None:
            return None

        stream, length, _extra, _patched = res
        try:
            raw = stream.read(length)
        finally:
            stream.close()

        try:
            pcm = parse_sound_record(raw)
        except Exception:
            return None

        # Preserve the actual index (UltimaSDK behavior after translation).
        return SoundPcm(name=pcm.name, pcm_s16le=pcm.pcm_s16le)

    def export_wav(self, sound_id: int, out_path: str | Path, *, entries: list | None = None) -> bool:
        pcm = self.read_sound_raw(sound_id, entries=entries)
        if pcm is None:
            return False
        write_wav_pcm_s16le(out_path, pcm)
        return True

    def import_wav(self, sound_id: int, wav_path: str | Path, *, name: str | None = None) -> None:
        pcm = read_wav_pcm_s16le(wav_path)
        final_name = pcm.name if name is None else str(name)

        payload = build_sound_record(final_name, pcm.pcm_s16le)

        pair = self._require_writable()
        entries = pair.load_index() if pair.idx_path.exists() else []
        _, entries = pair.append_raw(payload, index=int(sound_id), entries=entries)
        pair.save_index(entries)


if TYPE_CHECKING:
    from .files import Files
