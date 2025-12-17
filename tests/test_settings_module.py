from __future__ import annotations

import os
from pathlib import Path

from uo_py_sdk import UoPySdkSettings


def test_settings_load_env_only(tmp_path: Path, monkeypatch) -> None:
    uo_dir = tmp_path / "uo"
    out_dir = tmp_path / "out"

    monkeypatch.setenv("UO_DIR", str(uo_dir))
    monkeypatch.setenv("UO_OUTPUT_DIR", "{uo_dir}/Exports")
    monkeypatch.setenv("UO_TEMP_DIR", str(out_dir))

    s = UoPySdkSettings.load(dotenv_path=tmp_path / "nope.env")
    assert s.uo_dir == uo_dir
    assert s.output_dir == uo_dir / "Exports"
    assert s.temp_dir == out_dir


def test_settings_load_missing_env(monkeypatch) -> None:
    monkeypatch.delenv("UO_DIR", raising=False)
    monkeypatch.delenv("UO_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("UO_TEMP_DIR", raising=False)

    s = UoPySdkSettings.load(dotenv_path="definitely_missing.env")
    assert s.uo_dir is None
    assert s.output_dir is None
    assert s.temp_dir is None
