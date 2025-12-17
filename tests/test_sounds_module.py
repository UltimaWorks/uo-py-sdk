from __future__ import annotations

import wave
from pathlib import Path

from uo_py_sdk.ultima import Files
from uo_py_sdk.ultima.sounds import Sounds


def _write_test_wav(path: Path, *, sample_rate: int = 22050) -> bytes:
    # 0.05s of silence (mono, 16-bit)
    frames = b"\x00\x00" * int(sample_rate * 0.05)

    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(frames)

    return frames


def test_sounds_can_decode_some_entry() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    sounds = Sounds.from_files(files)

    entries = sounds.file_index.load()

    decoded = None
    for i in range(min(2048, len(entries))):
        if not sounds.file_index.valid(i, entries=entries):
            continue
        decoded = sounds.read_sound_raw(i, entries=entries)
        if decoded is not None:
            break

    assert decoded is not None
    assert isinstance(decoded.name, str)
    assert decoded.sample_rate == 22050
    assert decoded.channels == 1


def test_sounds_import_export_wav_and_def_translation(tmp_path: Path) -> None:
    # Arrange a minimal UO dir with a Sound.def translation mapping.
    uo_dir = tmp_path
    (uo_dir / "Sound.def").write_text("0 { 1 } 0\n", encoding="utf-8")

    wav_in = uo_dir / "in.wav"
    frames = _write_test_wav(wav_in)

    files = Files.from_path(uo_dir)
    sounds = Sounds.from_files(files)

    # Act: write sound #1 from wav.
    sounds.import_wav(1, wav_in, name="test_sound")

    # Export it back out.
    wav_out = uo_dir / "out.wav"
    assert sounds.export_wav(1, wav_out)

    # Read via translated id (#0 -> #1).
    resolved = sounds.resolve_sound_index(0)
    assert resolved == (1, True)
    s0 = sounds.read_sound_raw(0)
    assert s0 is not None
    assert s0.name == "test_sound"
    assert s0.pcm_s16le == frames

    # Verify exported WAV properties.
    with wave.open(str(wav_out), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 22050
        assert w.readframes(w.getnframes()) == frames
