from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_PAIR_OVERRIDES: dict[str, tuple[str, str, str | None]] = {
    # Many client assets use these historical filenames rather than `{type}idx.mul`.
    # We keep the public API keyed by an asset_type string.
    "texmaps": ("texmaps.mul", "texidx.mul", None),
    "gump": ("gumpart.mul", "gumpidx.mul", "gump.def"),
    "gumps": ("gumpart.mul", "gumpidx.mul", "gump.def"),
    "gumpart": ("gumpart.mul", "gumpidx.mul", "gump.def"),
    # Multis use `.idx` rather than `{type}idx.mul`.
    "multi": ("multi.mul", "multi.idx", None),
    "multis": ("multi.mul", "multi.idx", None),

    # Animations use `.idx` rather than `{type}idx.mul`.
    "anim": ("anim.mul", "anim.idx", None),
    "anim2": ("anim2.mul", "anim2.idx", None),
    "anim3": ("anim3.mul", "anim3.idx", None),
    "anim4": ("anim4.mul", "anim4.idx", None),
    "anim5": ("anim5.mul", "anim5.idx", None),
    "anim6": ("anim6.mul", "anim6.idx", None),

    # Skills use `.idx` rather than `{type}idx.mul`.
    "skills": ("skills.mul", "skills.idx", None),
}


def _resolve_existing_case_insensitive(base: Path, filename: str) -> Path:
    """Resolve `filename` under `base`, trying a case-insensitive match if needed."""

    direct = base / filename
    if direct.exists():
        return direct

    # Only attempt scanning when the directory exists.
    if not base.exists() or not base.is_dir():
        return direct

    target = filename.lower()
    try:
        for child in base.iterdir():
            if child.name.lower() == target:
                return child
    except OSError:
        pass

    return direct


@dataclass(frozen=True, slots=True)
class MulPairPaths:
    """Resolves the standard UO file naming convention.

    For a given `asset_type` (e.g. "art"), the pair is:
    - `{asset_type}.mul`
    - `{asset_type}idx.mul`

    Many types optionally have:
    - `{asset_type}.def`
    """

    asset_type: str
    mul_path: Path
    idx_path: Path
    def_path: Path | None

    @classmethod
    def from_uopath(cls, uo_dir: str | Path, asset_type: str) -> "MulPairPaths":
        base = Path(uo_dir)
        asset_type = asset_type.strip()
        key = asset_type.lower()

        override = _PAIR_OVERRIDES.get(key)
        if override is None:
            mul_filename = f"{asset_type}.mul"
            idx_filename = f"{asset_type}idx.mul"
            def_filename = f"{asset_type}.def"
        else:
            mul_filename, idx_filename, def_filename = override

        mul_path = _resolve_existing_case_insensitive(base, mul_filename)
        idx_path = _resolve_existing_case_insensitive(base, idx_filename)
        if def_filename is None:
            def_path = base / f"{asset_type}.def"
        else:
            def_path = _resolve_existing_case_insensitive(base, def_filename)
        return cls(
            asset_type=asset_type,
            mul_path=mul_path,
            idx_path=idx_path,
            def_path=def_path if def_path.exists() else None,
        )
