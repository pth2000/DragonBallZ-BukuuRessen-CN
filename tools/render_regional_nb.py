#!/usr/bin/env python3
from __future__ import annotations

import argparse
import struct
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nds import NDSRom
from dbzbr.nitro_bg import decode_4bpp_tile, decode_bgr555_palette


def normalized_stem(stem: str) -> str:
    for suffix in ("_JA", "_US", "JA", "US"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def triples(archive: PackedArchive) -> dict[str, tuple[str, str, str]]:
    names = set(archive.names())
    result = {}
    for name in dict.fromkeys(archive.names()):
        if not name.endswith(".nbfc"):
            continue
        stem = name[:-5]
        palette = f"{stem}.nbfp"
        screen = f"{stem}.nbfs"
        if palette in names and screen in names:
            result[normalized_stem(stem)] = (name, palette, screen)
    return result


def render(archive: PackedArchive, names: tuple[str, str, str]) -> Image.Image:
    characters = archive.unpack(names[0])
    screen = archive.unpack(names[2])
    if len(screen) % 64:
        raise ValueError(f"NBFS screen map has unexpected size {len(screen)}")
    map_values = struct.unpack(f"<{len(screen) // 2}H", screen)
    screen_tiles_high = len(map_values) // 32
    pixels = [[0] * 256 for _ in range(screen_tiles_high * 8)]
    tile_count = len(characters) // 32
    for map_index, value in enumerate(map_values):
        tile_index = value & 0x3FF
        if tile_index >= tile_count:
            raise ValueError(f"tile index {tile_index} exceeds {tile_count}")
        tile = decode_4bpp_tile(characters, tile_index)
        hflip = bool(value & 0x400)
        vflip = bool(value & 0x800)
        palette_bank = value >> 12
        origin_x = (map_index % 32) * 8
        origin_y = (map_index // 32) * 8
        for y in range(8):
            for x in range(8):
                sx = 7 - x if hflip else x
                sy = 7 - y if vflip else y
                pixels[origin_y + y][origin_x + x] = palette_bank * 16 + tile[sy][sx]
    palette = decode_bgr555_palette(archive.unpack(names[1]))
    image = Image.new("RGBA", (256, len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Render paired JA/US NBFC/NBFP/NBFS UI screens.")
    parser.add_argument("ja_path", help="JA NitroFS resource path")
    parser.add_argument("us_path", help="US NitroFS resource path")
    parser.add_argument(
        "--rom",
        type=Path,
        default=PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "build/regional_ui_previews",
    )
    args = parser.parse_args()

    rom = NDSRom.from_file(args.rom)
    ja_archive = PackedArchive(rom.get_file(args.ja_path))
    us_archive = PackedArchive(rom.get_file(args.us_path))
    ja_triples = triples(ja_archive)
    us_triples = triples(us_archive)
    keys = sorted(set(ja_triples) | set(us_triples))
    target = args.output_dir / Path(args.ja_path).stem
    target.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", (512, len(keys) * 280), (36, 39, 48, 255))
    draw = ImageDraw.Draw(sheet)
    for row, key in enumerate(keys):
        for column, (label, archive, available) in enumerate(
            (("JA", ja_archive, ja_triples), ("US", us_archive, us_triples))
        ):
            y = row * 280
            draw.text((column * 256 + 4, y + 2), f"{key} / {label}", fill="white")
            names = available.get(key)
            if names is None:
                draw.text((column * 256 + 4, y + 24), "missing", fill="red")
                continue
            image = render(archive, names)
            image.save(target / f"{key}_{label}.png")
            sheet.alpha_composite(image, (column * 256, y + 20))
    output = target / "JA_US_contact_sheet.png"
    sheet.save(output)
    print(output)


if __name__ == "__main__":
    main()
