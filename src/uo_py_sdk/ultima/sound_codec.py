from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

from ..errors import MulFormatError


SOUND_NAME_BYTES = 32
SOUND_CHANNELS = 1
SOUND_SAMPLE_RATE = 22050
SOUND_SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM


@dataclass(frozen=True, slots=True)
class SoundPcm:
    name: str
    pcm_s16le: bytes
    channels: int = SOUND_CHANNELS
    sample_rate: int = SOUND_SAMPLE_RATE
    sample_width_bytes: int = SOUND_SAMPLE_WIDTH_BYTES

    @property
    def frame_count(self) -> int:
        denom = int(self.channels) * int(self.sample_width_bytes)
        return len(self.pcm_s16le) // denom if denom > 0 else 0

    @property
    def duration_seconds(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return float(self.frame_count) / float(self.sample_rate)


def parse_sound_record(raw: bytes) -> SoundPcm:
    if len(raw) < SOUND_NAME_BYTES:
        raise MulFormatError("sound record truncated")

    name_bytes = raw[:SOUND_NAME_BYTES]
    pcm = raw[SOUND_NAME_BYTES:]

    name = name_bytes.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
    return SoundPcm(name=name, pcm_s16le=pcm)


def build_sound_record(name: str, pcm_s16le: bytes) -> bytes:
    nb = (name or "").encode("ascii", errors="replace")
    nb = nb[:SOUND_NAME_BYTES]
    nb = nb.ljust(SOUND_NAME_BYTES, b"\x00")
    return nb + (pcm_s16le or b"")


def read_wav_pcm_s16le(path: str | Path) -> SoundPcm:
    p = Path(path)
    with wave.open(str(p), "rb") as w:
        channels = w.getnchannels()
        sample_width = w.getsampwidth()
        sample_rate = w.getframerate()
        frames = w.readframes(w.getnframes())

    if channels != SOUND_CHANNELS:
        raise ValueError(f"expected {SOUND_CHANNELS} channel WAV, got {channels}")
    if sample_width != SOUND_SAMPLE_WIDTH_BYTES:
        raise ValueError(f"expected 16-bit PCM WAV (sampwidth=2), got {sample_width}")
    if sample_rate != SOUND_SAMPLE_RATE:
        raise ValueError(f"expected {SOUND_SAMPLE_RATE} Hz WAV, got {sample_rate}")

    return SoundPcm(name=p.stem, pcm_s16le=frames, channels=channels, sample_rate=sample_rate, sample_width_bytes=sample_width)


def write_wav_pcm_s16le(path: str | Path, pcm: SoundPcm) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(p), "wb") as w:
        w.setnchannels(int(pcm.channels))
        w.setsampwidth(int(pcm.sample_width_bytes))
        w.setframerate(int(pcm.sample_rate))
        w.writeframes(pcm.pcm_s16le)
