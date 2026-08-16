#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nds import NDSRom
from dbzbr.nitro_bg import decode_4bpp_screen, decode_4bpp_tile, decode_bgr555_palette

PAUSE_PATH = "romdata/scene/common/pausemenu.bin"


def render_ntft(texture: bytes, palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    if len(texture) % 32:
        raise ValueError("4bpp NTFT is not a whole number of tiles")
    tile_count = len(texture) // 32
    tiles_wide = 16 if len(texture) == 4096 else 32
    if tile_count % tiles_wide:
        raise ValueError("4bpp NTFT does not fit the selected atlas width")
    image = Image.new(
        "RGBA", (tiles_wide * 8, tile_count // tiles_wide * 8), (36, 39, 48, 255)
    )
    for tile_index in range(tile_count):
        tile = decode_4bpp_tile(texture, tile_index)
        origin_x = tile_index % tiles_wide * 8
        origin_y = tile_index // tiles_wide * 8
        for y in range(8):
            for x in range(8):
                value = tile[y][x]
                if value:
                    image.putpixel((origin_x + x, origin_y + y), palette[value])
    return image


def render_nb(characters: bytes, screen: bytes, palette_data: bytes) -> Image.Image:
    pixels = decode_4bpp_screen(characters, screen)
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (256, len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def save_pair(left: Image.Image, right: Image.Image, labels: tuple[str, str], output: Path) -> None:
    height = max(left.height, right.height)
    sheet = Image.new("RGBA", (512, height + 20), (36, 39, 48, 255))
    draw = ImageDraw.Draw(sheet)
    for column, (label, image) in enumerate(zip(labels, (left, right))):
        draw.text((column * 256 + 4, 2), label, fill="white")
        sheet.alpha_composite(image, (column * 256, 20))
    sheet.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render JP/EN pause-menu resources.")
    parser.add_argument(
        "--rom",
        type=Path,
        default=PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "build/pause_menu_audit"
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rom = NDSRom.from_file(args.rom)
    archive = PackedArchive(rom.get_file(PAUSE_PATH))
    names = set(archive.names())

    ntft_stems = sorted(
        name[8:-5]
        for name in names
        if name.startswith("menu_jp_") and name.endswith(".ntft")
    )
    for stem in ntft_stems:
        jp_name = f"menu_jp_{stem}.ntft"
        en_name = f"menu_en_{stem}.ntft"
        if en_name not in names:
            continue
        palette_name = f"menu_en_{stem}.ntfp"
        if palette_name not in names:
            palette_name = "menu_en_continue.ntfp"
        save_pair(
            render_ntft(archive.unpack(jp_name), archive.unpack(palette_name)),
            render_ntft(archive.unpack(en_name), archive.unpack(palette_name)),
            (f"{stem} / JP", f"{stem} / EN"),
            args.output_dir / f"label_{stem}_JP_EN.png",
        )

    nb_stems = sorted(
        name[8:-5]
        for name in names
        if name.startswith("menu_jp_") and name.endswith(".nbfc")
    )
    for stem in nb_stems:
        jp_stem = f"menu_jp_{stem}"
        en_stem = f"menu_en_{stem}"
        save_pair(
            render_nb(
                archive.unpack(f"{jp_stem}.nbfc"),
                archive.unpack(f"{jp_stem}.nbfs"),
                archive.unpack(f"{en_stem}.nbfp"),
            ),
            render_nb(
                archive.unpack(f"{en_stem}.nbfc"),
                archive.unpack(f"{en_stem}.nbfs"),
                archive.unpack(f"{en_stem}.nbfp"),
            ),
            (f"{stem} / JP", f"{stem} / EN"),
            args.output_dir / f"screen_{stem}_JP_EN.png",
        )

    print(args.output_dir)


if __name__ == "__main__":
    main()
