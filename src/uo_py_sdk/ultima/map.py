from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..mul.pair import MulPair
from .map_codec import (
    MapTile,
    StaticTile,
    decode_map_block,
    decode_static_block,
    encode_map_block,
    encode_static_block,
    _MAP_BLOCK_SIZE,
)
from .art import Art

if TYPE_CHECKING:
    from .files import Files


@dataclass(frozen=True, slots=True)
class MapDefinition:
    map_id: int
    width: int
    height: int

    @property
    def block_width(self) -> int:
        return self.width >> 3

    @property
    def block_height(self) -> int:
        return self.height >> 3


# Standard UO map definitions
MAP_DEFINITIONS = {
    0: MapDefinition(0, 6144, 4096),  # Felucca
    1: MapDefinition(1, 6144, 4096),  # Trammel
    2: MapDefinition(2, 2304, 1600),  # Ilshenar
    3: MapDefinition(3, 2560, 2048),  # Malas
    4: MapDefinition(4, 1448, 1448),  # Tokuno
    5: MapDefinition(5, 1280, 4096),  # TerMur
}


@dataclass(slots=True)
class MapBlock:
    x: int
    y: int
    land: list[MapTile]
    statics: list[StaticTile]


@dataclass(frozen=True, slots=True)
class BlockRect:
    """Inclusive bounds in block coordinates."""

    min_x: int
    min_y: int
    max_x: int
    max_y: int


@dataclass(slots=True)
class UOMap:
    """Access to map{N}.mul and statics{N}.mul/staidx{N}.mul."""

    files: "Files"
    map_id: int
    definition: MapDefinition
    map_path: Path
    statics_pair: MulPair | None = None

    @classmethod
    def from_files(cls, files: "Files", map_id: int) -> "UOMap":
        # Resolve map definition (default to Felucca size if unknown)
        defn = MAP_DEFINITIONS.get(map_id, MAP_DEFINITIONS[0])
        
        # Map file
        map_filename = f"map{map_id}.mul"
        map_path = files.get_file_path(map_filename)
        if map_path is None:
            # Fallback or error? For now, assume it might not exist and let operations fail gracefully
            map_path = files.uo_dir / map_filename

        # Statics pair
        # statics{N}.mul + staidx{N}.mul
        # We can use MulPair, but we need to construct paths manually since it's not a standard type name
        statics_path = files.get_file_path(f"statics{map_id}.mul") or (files.uo_dir / f"statics{map_id}.mul")
        staidx_path = files.get_file_path(f"staidx{map_id}.mul") or (files.uo_dir / f"staidx{map_id}.mul")
        
        statics_pair = MulPair(mul_path=statics_path, idx_path=staidx_path)

        return cls(
            files=files,
            map_id=map_id,
            definition=defn,
            map_path=map_path,
            statics_pair=statics_pair,
        )

    @property
    def block_width(self) -> int:
        return self.definition.block_width

    @property
    def block_height(self) -> int:
        return self.definition.block_height

    def in_bounds(self, block_x: int, block_y: int) -> bool:
        return 0 <= int(block_x) < self.block_width and 0 <= int(block_y) < self.block_height

    def clamp_rect(self, rect: BlockRect) -> BlockRect:
        min_x = max(0, int(rect.min_x))
        min_y = max(0, int(rect.min_y))
        max_x = min(self.block_width - 1, int(rect.max_x))
        max_y = min(self.block_height - 1, int(rect.max_y))
        return BlockRect(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    def iter_block_coords(self, rect: BlockRect | None = None):
        """Iterate (block_x, block_y) in-bounds.

        If `rect` is provided, iterates only within those inclusive bounds.
        """

        if rect is None:
            min_x, min_y, max_x, max_y = 0, 0, self.block_width - 1, self.block_height - 1
        else:
            rr = self.clamp_rect(rect)
            min_x, min_y, max_x, max_y = rr.min_x, rr.min_y, rr.max_x, rr.max_y

        for bx in range(min_x, max_x + 1):
            for by in range(min_y, max_y + 1):
                yield bx, by

    def iter_blocks(self, rect: BlockRect | None = None):
        """Iterate MapBlocks within bounds (skips missing land blocks)."""

        for bx, by in self.iter_block_coords(rect):
            blk = self.read_block(bx, by)
            if blk is not None:
                yield blk

    def _get_block_offset(self, block_x: int, block_y: int) -> int:
        return ((block_x * self.definition.block_height) + block_y) * _MAP_BLOCK_SIZE

    def read_land_block(self, block_x: int, block_y: int) -> list[MapTile] | None:
        if not self.in_bounds(block_x, block_y):
            return None
        if not self.map_path.exists():
            return None
            
        offset = self._get_block_offset(block_x, block_y)
        
        try:
            with self.map_path.open("rb") as f:
                f.seek(offset)
                data = f.read(_MAP_BLOCK_SIZE)
                if len(data) != _MAP_BLOCK_SIZE:
                    return None
                return decode_map_block(data)
        except OSError:
            return None

    def read_static_block(self, block_x: int, block_y: int) -> list[StaticTile]:
        if not self.in_bounds(block_x, block_y):
            return []
        if self.statics_pair is None or not self.statics_pair.idx_path.exists():
            return []

        # Calculate index in staidx
        # Index = (block_x * block_height) + block_y
        index = (block_x * self.definition.block_height) + block_y
        
        # We can use MulPair.read_raw, but we need to be careful about loading the whole index
        # For large maps, loading the whole index might be slow/memory intensive?
        # staidx0.mul is ~4.5MB (768*512 * 12 bytes). That's fine to load into memory.
        
        try:
            # TODO: Maybe cache the index? For now, load it every time or rely on MulPair caching if we add it.
            # MulPair doesn't cache.
            # Let's just read the specific entry from the idx file to avoid loading 4MB every call.
            
            with self.statics_pair.idx_path.open("rb") as f:
                f.seek(index * 12)
                entry_data = f.read(12)
                if len(entry_data) != 12:
                    return []

                offset, length, _extra = struct.unpack("<iii", entry_data)
                
                if offset < 0 or length <= 0:
                    return []
                    
            with self.statics_pair.mul_path.open("rb") as f:
                f.seek(offset)
                data = f.read(length)
                return decode_static_block(data)
                
        except (OSError, struct.error):
            return []

    def read_block(self, block_x: int, block_y: int) -> MapBlock | None:
        land = self.read_land_block(block_x, block_y)
        if land is None:
            return None
            
        statics = self.read_static_block(block_x, block_y)
        return MapBlock(block_x, block_y, land, statics)

    # Image export

    def render_block(self, block_x: int, block_y: int, max_height: int = 300):
        """Render the block as an RGBA PIL image. Returns `None` if Pillow is unavailable or map missing."""
        try:
            from PIL import Image
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Pillow is required for map image export. Install uo-py-sdk[image] or uo-py-sdk[dev].") from e

        land = self.read_land_block(block_x, block_y)
        if land is None:
            return None

        statics = self.read_static_block(block_x, block_y)

        art = Art.from_files(self.files)

        # Build list of draw ops to compute bounds first
        draw_ops = []  # tuples (img, px, py)
        xs = []
        ys = []

        # Land tiles (44x44) arranged isometrically
        for y in range(8):
            for x in range(8):
                idx = (y << 3) + x
                tile = land[idx]
                land_id = int(tile.id) & 0x3FFF

                land_img = art.land_image(land_id)

                if land_img is None:
                    # fallback: blank 44x44
                    land_img = Image.new("RGBA", (44, 44), (255, 255, 255, 255))

                px = (x - y) * 22
                py = (x + y) * 22
                draw_ops.append((land_img, px, py))
                xs.extend([px, px + land_img.width])
                ys.extend([py, py + land_img.height])

        for s in statics:
            sx = int(s.x)
            sy = int(s.y)
            item_id = int(s.id)
            z = int(s.z)

            if z > int(max_height):
                continue
            # position
            px = (sx - sy) * 22
            py = (sx + sy) * 22

            # draw static image (centered, offset by z and height)
            static_img = art.static_image(item_id, check_max_id=False)

            if static_img is None:
                # skip if no image
                continue

            sx_px = int(px - (static_img.width / 2))
            sy_px = int(py - (z << 2) - static_img.height)
            draw_ops.append((static_img, sx_px, sy_px))
            xs.extend([sx_px, sx_px + static_img.width])
            ys.extend([sy_px, sy_px + static_img.height])

        if not xs or not ys:
            return None

        min_x = min(xs)
        min_y = min(ys)
        max_x = max(xs)
        max_y = max(ys)

        width = int(max_x - min_x)
        height = int(max_y - min_y)
        if width <= 0 or height <= 0:
            return None

        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))

        for img, px, py in draw_ops:
            x_ = int(px - min_x)
            y_ = int(py - min_y)
            try:
                canvas.paste(img, (x_, y_), img)
            except Exception:
                canvas.paste(img, (x_, y_))

        return canvas

    def export_block_image(self, block_x: int, block_y: int, out_path: str) -> bool:
        img = self.render_block(block_x, block_y)
        if img is None:
            return False
        img.save(out_path)
        return True

