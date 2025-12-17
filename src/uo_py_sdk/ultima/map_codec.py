from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Sequence

from ..errors import MulFormatError


@dataclass(frozen=True, slots=True)
class MapTile:
    """A land tile in a map block."""
    id: int  # u16
    z: int   # i8


@dataclass(frozen=True, slots=True)
class StaticTile:
    """A static item in a map block."""
    id: int   # u16
    x: int    # u8 (0-7 relative to block)
    y: int    # u8 (0-7 relative to block)
    z: int    # i8
    hue: int  # i16


_MAP_BLOCK_HEADER_SIZE = 4
_MAP_TILE_SIZE = 3
_MAP_BLOCK_TILES = 64
_MAP_BLOCK_SIZE = _MAP_BLOCK_HEADER_SIZE + (_MAP_BLOCK_TILES * _MAP_TILE_SIZE)  # 196 bytes

_STATIC_TILE_STRUCT = struct.Struct("<HBBbh")  # id:u16, x:u8, y:u8, z:i8, hue:i16
_STATIC_TILE_SIZE = _STATIC_TILE_STRUCT.size  # 7 bytes


def decode_map_block(raw: bytes) -> list[MapTile]:
    """Decode a 196-byte map block into 64 MapTiles.
    
    The 4-byte header is ignored.
    """
    if len(raw) != _MAP_BLOCK_SIZE:
        raise MulFormatError(f"Map block must be {_MAP_BLOCK_SIZE} bytes, got {len(raw)}")

    # Skip 4-byte header
    off = 4
    tiles = []
    for _ in range(_MAP_BLOCK_TILES):
        # Manual unpack for speed/simplicity on small struct
        # tile: id(u16), z(i8)
        # struct.unpack_from("<Hb", raw, off)
        
        # Little-endian u16
        tile_id = raw[off] | (raw[off+1] << 8)
        
        # Signed i8
        z = raw[off+2]
        if z > 127:
            z -= 256
            
        tiles.append(MapTile(tile_id, z))
        off += 3
        
    return tiles


def encode_map_block(tiles: Sequence[MapTile], header: int = 0) -> bytes:
    """Encode 64 MapTiles into a 196-byte map block."""
    if len(tiles) != _MAP_BLOCK_TILES:
        raise ValueError(f"Map block must have exactly {_MAP_BLOCK_TILES} tiles")

    out = bytearray(_MAP_BLOCK_SIZE)
    
    # Write header
    struct.pack_into("<I", out, 0, header)
    
    off = 4
    for t in tiles:
        # id(u16)
        out[off] = t.id & 0xFF
        out[off+1] = (t.id >> 8) & 0xFF
        # z(i8)
        out[off+2] = t.z & 0xFF
        off += 3
        
    return bytes(out)


def decode_static_block(raw: bytes) -> list[StaticTile]:
    """Decode a raw static block payload."""
    if len(raw) % _STATIC_TILE_SIZE != 0:
        raise MulFormatError(f"Static block size {len(raw)} is not a multiple of {_STATIC_TILE_SIZE}")
        
    count = len(raw) // _STATIC_TILE_SIZE
    tiles = []
    for i in range(count):
        off = i * _STATIC_TILE_SIZE
        tid, x, y, z, hue = _STATIC_TILE_STRUCT.unpack_from(raw, off)
        tiles.append(StaticTile(tid, x, y, z, hue))
        
    return tiles


def encode_static_block(tiles: Sequence[StaticTile]) -> bytes:
    """Encode a list of StaticTiles."""
    out = bytearray(len(tiles) * _STATIC_TILE_SIZE)
    off = 0
    for t in tiles:
        _STATIC_TILE_STRUCT.pack_into(out, off, t.id, t.x, t.y, t.z, t.hue)
        off += _STATIC_TILE_SIZE
    return bytes(out)
