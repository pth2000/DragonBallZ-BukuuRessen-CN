"""Raw 4bpp NBFC/NBFP/NBFS background helpers used by menu resources."""
from __future__ import annotations

import struct

SCREEN_TILES_WIDE = 32
SCREEN_TILES_HIGH = 32
TILE_SIZE = 8
SCREEN_WIDTH = SCREEN_TILES_WIDE * TILE_SIZE
SCREEN_HEIGHT = SCREEN_TILES_HIGH * TILE_SIZE


def decode_4bpp_linear(data: bytes, *, width: int = 256) -> list[list[int]]:
    """Decode a linear (non-tiled) 4bpp texture such as NTFT map titles.

    The low nibble of each byte is the left pixel. These textures are *not*
    arranged in 8x8 tiles; decoding them as tiles scatters a local edit across
    the whole image.
    """
    if width % 2:
        raise ValueError("4bpp texture width must be even")
    if len(data) * 2 % width:
        raise ValueError("4bpp texture does not fit the selected width")
    values = [value for packed in data for value in (packed & 0x0F, packed >> 4)]
    return [values[y * width : (y + 1) * width] for y in range(len(values) // width)]


def encode_4bpp_linear(pixels: list[list[int]]) -> bytes:
    if not pixels or any(len(row) != len(pixels[0]) for row in pixels):
        raise ValueError("indexed texture must be rectangular")
    values = [value for row in pixels for value in row]
    if len(values) % 2 or any(not 0 <= value < 16 for value in values):
        raise ValueError("4bpp pixels must contain an even number of 0..15 values")
    return bytes(
        values[index] | (values[index + 1] << 4) for index in range(0, len(values), 2)
    )


def decode_4bpp_tile(data: bytes, tile_index: int) -> list[list[int]]:
    start = tile_index * 32
    tile = data[start : start + 32]
    if len(tile) != 32:
        raise ValueError(f"4bpp tile {tile_index} exceeds character data")
    return [
        [
            (tile[y * 4 + x // 2] >> (4 * (x & 1))) & 0xF
            for x in range(TILE_SIZE)
        ]
        for y in range(TILE_SIZE)
    ]


def decode_4bpp_screen(characters: bytes, screen: bytes) -> list[list[int]]:
    if len(characters) % 32:
        raise ValueError("NBFC character data is not a whole number of 4bpp tiles")
    row_bytes = SCREEN_TILES_WIDE * 2
    if not screen or len(screen) % row_bytes:
        raise ValueError(f"NBFS screen map has unexpected size {len(screen)}")
    tile_count = len(characters) // 32
    map_values = struct.unpack(f"<{len(screen) // 2}H", screen)
    screen_tiles_high = len(map_values) // SCREEN_TILES_WIDE
    output = [[0] * SCREEN_WIDTH for _ in range(screen_tiles_high * TILE_SIZE)]
    for map_index, value in enumerate(map_values):
        tile_index = value & 0x3FF
        if tile_index >= tile_count:
            raise ValueError(f"tile index {tile_index} exceeds {tile_count}")
        hflip = bool(value & 0x400)
        vflip = bool(value & 0x800)
        palette_bank = value >> 12
        tile = decode_4bpp_tile(characters, tile_index)
        origin_x = (map_index % SCREEN_TILES_WIDE) * TILE_SIZE
        origin_y = (map_index // SCREEN_TILES_WIDE) * TILE_SIZE
        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):
                sx = TILE_SIZE - 1 - x if hflip else x
                sy = TILE_SIZE - 1 - y if vflip else y
                output[origin_y + y][origin_x + x] = palette_bank * 16 + tile[sy][sx]
    return output


def _encode_4bpp_tile(tile: tuple[int, ...]) -> bytes:
    if len(tile) != 64 or any(not 0 <= value < 16 for value in tile):
        raise ValueError("a 4bpp tile must contain 64 palette indices in range 0..15")
    output = bytearray(32)
    for y in range(TILE_SIZE):
        for x in range(0, TILE_SIZE, 2):
            output[y * 4 + x // 2] = tile[y * TILE_SIZE + x] | (
                tile[y * TILE_SIZE + x + 1] << 4
            )
    return bytes(output)


def encode_4bpp_screen(pixels: list[list[int]]) -> tuple[bytes, bytes]:
    if (
        not pixels
        or len(pixels) % TILE_SIZE
        or len(pixels) > SCREEN_HEIGHT
        or any(len(row) != SCREEN_WIDTH for row in pixels)
    ):
        raise ValueError("indexed screen must be 256px wide and 8..256px high in 8px rows")
    if any(not 0 <= value < 16 for row in pixels for value in row):
        raise ValueError("single-palette screen pixels must be in range 0..15")

    blank = (0,) * 64
    tiles: list[tuple[int, ...]] = [blank]
    by_pixels = {blank: 0}
    map_values: list[int] = []
    for tile_y in range(len(pixels) // TILE_SIZE):
        for tile_x in range(SCREEN_TILES_WIDE):
            tile = tuple(
                pixels[tile_y * TILE_SIZE + y][tile_x * TILE_SIZE + x]
                for y in range(TILE_SIZE)
                for x in range(TILE_SIZE)
            )
            tile_index = by_pixels.get(tile)
            if tile_index is None:
                tile_index = len(tiles)
                if tile_index >= 1024:
                    raise ValueError("screen needs more than 1024 unique 4bpp tiles")
                by_pixels[tile] = tile_index
                tiles.append(tile)
            map_values.append(tile_index)
    characters = b"".join(_encode_4bpp_tile(tile) for tile in tiles)
    screen = struct.pack(f"<{len(map_values)}H", *map_values)
    return characters, screen


def decode_bgr555_palette(data: bytes) -> list[tuple[int, int, int, int]]:
    if len(data) % 2:
        raise ValueError("BGR555 palette size must be even")
    colors = []
    for value in struct.unpack(f"<{len(data) // 2}H", data):
        colors.append(
            (
                (value & 31) * 255 // 31,
                ((value >> 5) & 31) * 255 // 31,
                ((value >> 10) & 31) * 255 // 31,
                255,
            )
        )
    return colors
