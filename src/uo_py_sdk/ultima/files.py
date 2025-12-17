from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..paths import MulPairPaths
from ..mul.pair import MulPair
from ..defs.parser import DefMapping, parse_def_file
from .file_index import FileIndex
from .verdata import Verdata


_VERDATA_FILE_IDS: dict[str, int] = {
    # Based on UltimaSDK's Verdata.cs file-id list and its module constructors.
    "art": 4,
    "anim": 6,
    "sound": 8,
    "texmaps": 10,
    "gump": 12,
    "gumps": 12,
    "gumpart": 12,
    "multi": 14,

    # Skills (skills.mul)
    "skills": 16,
}


@dataclass(frozen=True, slots=True)
class Files:
    """UltimaSDK-style entry point for resolving client data files.

    Unlike the C# static `Ultima.Files`, this is instance-based.
    """

    uo_dir: Path

    @classmethod
    def from_path(cls, uo_dir: str | Path) -> "Files":
        return cls(uo_dir=Path(uo_dir))

    @property
    def root_dir(self) -> Path:
        return self.uo_dir

    @property
    def verdata(self) -> Verdata:
        # Cheap to construct; parses the patch table once.
        return Verdata.from_uo_dir(self.uo_dir)

    def get_file_path(self, filename: str) -> Path | None:
        """Resolve a raw client filename (e.g. `Art.mul`) to an existing path."""

        p = self.uo_dir / filename
        return p if p.exists() else None

    def mul_pair(self, asset_type: str) -> MulPair:
        paths = MulPairPaths.from_uopath(self.uo_dir, asset_type)
        return MulPair(mul_path=paths.mul_path, idx_path=paths.idx_path)

    def file_index(self, asset_type: str) -> FileIndex:
        paths = MulPairPaths.from_uopath(self.uo_dir, asset_type)
        file_id = _VERDATA_FILE_IDS.get(asset_type.lower())
        return FileIndex(
            idx_path=paths.idx_path,
            mul_path=paths.mul_path,
            verdata=self.verdata,
            file_id=file_id,
        )

    def def_mapping(self, asset_type: str) -> DefMapping:
        paths = MulPairPaths.from_uopath(self.uo_dir, asset_type)
        if paths.def_path is None:
            return DefMapping(mapping={})
        return parse_def_file(paths.def_path)

    # Convenience helpers (tooling ergonomics)

    def art(self) -> "Art":
        from .art import Art

        return Art.from_files(self)

    def gumps(self) -> "Gumps":
        from .gumps import Gumps

        return Gumps.from_files(self)

    def textures(self) -> "Textures":
        from .textures import Textures

        return Textures.from_files(self)

    def sounds(self) -> "Sounds":
        from .sounds import Sounds

        return Sounds.from_files(self)

    def multis(self) -> "Multis":
        from .multis import Multis

        return Multis.from_files(self)

    def animations(self, *, file_set: int = 1) -> "Animations":
        from .animations import Animations

        return Animations.from_files(self, file_set=file_set)

    def lights(self) -> "Lights":
        from .lights import Lights

        return Lights.from_files(self)

    def skills(self) -> "Skills":
        from .skills import Skills

        return Skills.from_files(self)

    def cliloc(self, language: str) -> "Cliloc":
        from .cliloc import Cliloc

        p = self.get_file_path(f"cliloc.{language}")
        if p is None:
            return Cliloc(language=str(language), entries=[])
        return Cliloc.from_path(p, language=str(language))


# Back-compat alias for earlier scaffold.
ClientFiles = Files
