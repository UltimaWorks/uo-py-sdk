from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UoPySdkSettings:
    """Simple settings for tool authors.

    Design goals:
    - No required dependencies.
    - Works with plain environment variables (CI-friendly).
    - Optionally supports `.env` if `python-dotenv` is installed.

    Recommended env vars:
    - `UO_DIR`: Ultima Online client folder.
    - `UO_OUTPUT_DIR`: default output directory for exports.
    - `UO_TEMP_DIR`: scratch directory for tools.

    Paths can include placeholders:
    - `{uo_dir}` expands to the resolved UO_DIR.
    """

    uo_dir: Path | None = None
    output_dir: Path | None = None
    temp_dir: Path | None = None

    @staticmethod
    def _expand_placeholders(value: str, *, uo_dir: Path | None) -> str:
        if uo_dir is not None:
            value = value.replace("{uo_dir}", str(uo_dir))
        return value

    @classmethod
    def load(cls, *, dotenv_path: str | Path | None = None) -> "UoPySdkSettings":
        """Load settings from env vars (and optionally a `.env`).

        If `python-dotenv` is available, this will load the `.env` file into the
        environment first.
        """

        if dotenv_path is None:
            dotenv_path = ".env"

        try:
            from dotenv import load_dotenv  # type: ignore

            load_dotenv(dotenv_path=dotenv_path, override=False)
        except Exception:
            # No dependency or no file; env-only is still fine.
            pass

        raw_uo_dir = os.getenv("UO_DIR")
        uo_dir = Path(raw_uo_dir).expanduser() if raw_uo_dir else None

        raw_out = os.getenv("UO_OUTPUT_DIR")
        if raw_out and uo_dir is not None:
            raw_out = cls._expand_placeholders(raw_out, uo_dir=uo_dir)
        output_dir = Path(raw_out).expanduser() if raw_out else None

        raw_tmp = os.getenv("UO_TEMP_DIR")
        if raw_tmp and uo_dir is not None:
            raw_tmp = cls._expand_placeholders(raw_tmp, uo_dir=uo_dir)
        temp_dir = Path(raw_tmp).expanduser() if raw_tmp else None

        return cls(uo_dir=uo_dir, output_dir=output_dir, temp_dir=temp_dir)
