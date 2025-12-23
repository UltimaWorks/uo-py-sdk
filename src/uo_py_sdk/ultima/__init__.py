"""UltimaSDK-inspired façade modules.

These are thin convenience layers over the core MUL/IDX IO.
They intentionally keep the same high-level shape as common UltimaSDK-style APIs:
- a client root path
- per-asset-type helpers

The implementation is new and Pythonic (not a port/copy).
"""

from __future__ import annotations

from .files import ClientFiles, Files
from .file_index import FileIndex, FileIndexIntegrityReport, FileIndexSnapshot, FileIndexReader
from .verdata import Verdata
from .art import Art
from .gumps import Gumps
from .sounds import Sounds
from .tiledata import TileData, LandTile, ItemTile
from .multis import Multis
from .multi_codec import MultiTileEntry
from .textures import Textures
from .hues import Hues, Hue
from . import art_codec
from .map import UOMap, MapBlock, MapTile, StaticTile, BlockRect
from .animations import Animations
from .animation_codec import AnimationFrame
from .fonts import AsciiFonts, AsciiFont, AsciiGlyph, UnicodeFont, UnicodeFonts, UnicodeGlyph
from .speech_list import SpeechList, SpeechEntry
from .radarcol import RadarCol
from .lights import Lights
from .skills import Skills, SkillInfo
from .skill_groups import SkillGroups, SkillGroup
from .cliloc import Cliloc, ClilocEntry, CliLocFlag
from .animinfo import AnimInfo, AnimInfoEntry

# Import new abstractions introduced for extended client configuration and
# storage backends.  These are intentionally lazily imported here to
# maintain backwards compatibility – existing code that imports
# ``uo_py_sdk.ultima`` will find these names on the module without
# altering the original API surface.

from .client import ClientProfile, UltimaClient
from .asset_store import IAssetStore, MulIdxStore, MmapMulIdxStore, CachedAssetStore

__all__ = [
	"Art",
	"Animations",
	"AnimationFrame",
	"AsciiFonts",
	"AsciiFont",
	"AsciiGlyph",
	"ClientFiles",
	"FileIndex",
	"FileIndexIntegrityReport",
	"FileIndexSnapshot",
	"FileIndexReader",
	"Files",
	"Gumps",
	"Multis",
	"MultiTileEntry",
	"Sounds",
	"UnicodeFont",
	"UnicodeFonts",
	"UnicodeGlyph",
	"UOMap",
	"MapBlock",
	"MapTile",
	"StaticTile",
	"BlockRect",
	"ItemTile",
	"LandTile",
	"TileData",
	"Hue",
	"Hues",
	"Textures",
	"Verdata",
	"art_codec",
	"RadarCol",
	"Lights",
	"SpeechList",
	"SpeechEntry",
	"Skills",
	"SkillInfo",
	"SkillGroups",
	"SkillGroup",
	"Cliloc",
	"ClilocEntry",
	"CliLocFlag",
	"AnimInfo",
	"AnimInfoEntry",
	# New: asset store abstractions and client profile/entry point
	"ClientProfile",
	"UltimaClient",
	"IAssetStore",
	"MulIdxStore",
	"MmapMulIdxStore",
	"CachedAssetStore",
]
