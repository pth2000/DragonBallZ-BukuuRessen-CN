#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nds import NDSRom
from dbzbr.nitro_bg import decode_bgr555_palette


def normalized_stem(stem: str) -> str:
    for suffix in ("_JA", "_US", "JA", "US"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def textures(archive: PackedArchive) -> dict[str, tuple[str, str]]:
    names = set(archive.names())
    result = {}
    for name in dict.fromkeys(archive.names()):
        if not name.endswith(".ntft"):
            continue
        stem = name[:-5]
        palette = f"{stem}.ntfp"
        if palette in names:
            result[normalized_stem(stem)] = (name, palette)
    return result


def render(archive: PackedArchive, names: tuple[str, str]) -> Image.Image:
    texture = archive.unpack(names[0])
    palette = decode_bgr555_palette(archive.unpack(names[1]))
    if len(texture) == 256 * 256 and all((value & 31) < len(palette) for value in texture):
        image = Image.new("RGBA", (256, 256), (36, 39, 48, 255))
        for index, value in enumerate(texture):
            alpha = (value >> 5) * 255 // 7
            if alpha:
                red, green, blue, _ = palette[value & 31]
                image.putpixel((index % 256, index // 256), (red, green, blue, alpha))
        return image
    if len(palette) <= 2:
        bits_per_pixel = 1
    elif len(palette) <= 4:
        bits_per_pixel = 2
    elif len(palette) <= 16:
        bits_per_pixel = 4
    else:
        bits_per_pixel = 8
    tile_bytes = bits_per_pixel * 8
    if len(texture) % tile_bytes:
        raise ValueError(f"NTFT is not a whole number of {bits_per_pixel}bpp tiles")
    tile_count = len(texture) // tile_bytes
    if tile_count % 32:
        raise ValueError(f"NTFT tiles do not fit a 256px-wide atlas: {tile_count}")
    image = Image.new("RGBA", (256, tile_count // 32 * 8), (36, 39, 48, 255))
    for tile_index in range(tile_count):
        tile = texture[tile_index * tile_bytes : (tile_index + 1) * tile_bytes]
        origin_x = tile_index % 32 * 8
        origin_y = tile_index // 32 * 8
        for y in range(8):
            for x in range(8):
                bit_index = (y * 8 + x) * bits_per_pixel
                byte_index = bit_index // 8
                shift = bit_index % 8
                value = (tile[byte_index] >> shift) & ((1 << bits_per_pixel) - 1)
                if value:
                    color = palette[value] if value < len(palette) else (36, 39, 48, 255)
                    image.putpixel((origin_x + x, origin_y + y), color)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Render paired JA/US NTFT/NTFP UI textures.")
    parser.add_argument("ja_path")
    parser.add_argument("us_path")
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
    ja_textures = textures(ja_archive)
    us_textures = textures(us_archive)
    keys = sorted(set(ja_textures) | set(us_textures))
    target = args.output_dir / Path(args.ja_path).stem
    target.mkdir(parents=True, exist_ok=True)
    rendered: dict[tuple[str, str], Image.Image] = {}
    row_heights = []
    for key in keys:
        for label, archive, available in (
            ("JA", ja_archive, ja_textures),
            ("US", us_archive, us_textures),
        ):
            names = available.get(key)
            if names is not None:
                rendered[(key, label)] = render(archive, names)
        row_heights.append(
            max(
                (rendered[(key, label)].height for label in ("JA", "US") if (key, label) in rendered),
                default=256,
            )
            + 24
        )
    sheet = Image.new("RGBA", (512, sum(row_heights)), (36, 39, 48, 255))
    draw = ImageDraw.Draw(sheet)
    row_y = 0
    for row, key in enumerate(keys):
        for column, (label, _archive, available) in enumerate(
            (("JA", ja_archive, ja_textures), ("US", us_archive, us_textures))
        ):
            draw.text((column * 256 + 4, row_y + 2), f"{key} / {label}", fill="white")
            names = available.get(key)
            if names is None:
                draw.text((column * 256 + 4, row_y + 24), "missing", fill="red")
                continue
            image = rendered[(key, label)]
            image.save(target / f"{key}_{label}.png")
            sheet.alpha_composite(image, (column * 256, row_y + 20))
        row_y += row_heights[row]
    output = target / "JA_US_contact_sheet.png"
    sheet.save(output)
    print(output)


if __name__ == "__main__":
    main()
