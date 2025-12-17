from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima.speech_list import SpeechList


def test_speech_list_loads_some_entries() -> None:
    client_files = Path(__file__).parent / "client_files"
    speech = SpeechList.from_path(client_files / "speech.mul")

    assert isinstance(speech.entries, list)
    assert len(speech.entries) > 0

    # Ensure ordering is stable and fields are sane.
    e0 = speech.entries[0]
    assert e0.order == 0
    assert 0 <= e0.id <= 0xFFFF
    assert isinstance(e0.keyword, str)
