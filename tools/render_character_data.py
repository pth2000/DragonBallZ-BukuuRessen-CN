#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nds import NDSRom
from dbzbr.nitro_bg import decode_bgr555_palette

JA_PATH = "romdata/data/DataModeDataImage.bin"
EN_PATH = "romdata/data/DataModeDataImage_EN.bin"
BACKGROUND = (36, 39, 48, 255)


def palette_stem(item: str) -> str:
    if item in {"ex2", "ex3"}:
        item = "ex1"
    elif item.startswith("sp"):
        item = "sp1"
    elif item.startswith("team"):
        item = "team1"
    return f"data_gkn_{item}"


def render_4bpp(
    texture: bytes,
    palette_data: bytes,
    tile_columns: int,
    *,
    column_major: bool = False,
    frame_rows: int | None = None,
) -> Image.Image:
    if len(texture) % 32:
        raise ValueError("4bpp texture is not a whole number of tiles")
    tile_count = len(texture) // 32
    if tile_count % tile_columns:
        raise ValueError(f"{tile_count} tiles do not fit {tile_columns} columns")
    palette = decode_bgr555_palette(palette_data)
    tile_rows = tile_count // tile_columns
    if frame_rows is not None and tile_count % (tile_columns * frame_rows):
        raise ValueError("texture is not a whole number of requested frames")
    image = Image.new("RGBA", (tile_columns * 8, tile_rows * 8), BACKGROUND)
    for tile_index in range(tile_count):
        tile = texture[tile_index * 32 : (tile_index + 1) * 32]
        if column_major:
            rows = frame_rows or tile_rows
            tiles_per_frame = tile_columns * rows
            frame = tile_index // tiles_per_frame
            within_frame = tile_index % tiles_per_frame
            origin_x = within_frame // rows * 8
            origin_y = (frame * rows + within_frame % rows) * 8
        else:
            origin_x = tile_index % tile_columns * 8
            origin_y = tile_index // tile_columns * 8
        for y in range(8):
            for x in range(8):
                value = (tile[y * 4 + x // 2] >> (x % 2 * 4)) & 0x0F
                if value:
                    image.putpixel((origin_x + x, origin_y + y), palette[value])
    return image


def render_4bpp_linear(texture: bytes, palette_data: bytes, width: int) -> Image.Image:
    if len(texture) * 2 % width:
        raise ValueError("linear 4bpp texture does not fit the selected width")
    palette = decode_bgr555_palette(palette_data)
    height = len(texture) * 2 // width
    image = Image.new("RGBA", (width, height), BACKGROUND)
    for byte_index, packed in enumerate(texture):
        for nibble in range(2):
            pixel_index = byte_index * 2 + nibble
            value = (packed >> (nibble * 4)) & 0x0F
            if value:
                image.putpixel((pixel_index % width, pixel_index // width), palette[value])
    return image


def render_item(
    archive: PackedArchive,
    language: str,
    character: str,
    item: str,
    tile_columns: int,
    *,
    column_major: bool = False,
    frame_rows: int | None = None,
    linear: bool = False,
) -> Image.Image:
    stem = f"data_{character}_{item}"
    directory = f"{language}\\{character}\\"
    texture = archive.unpack(f"{directory}{stem}.ntft")
    palette = archive.unpack(
        f"{language}\\gkn\\{palette_stem(item)}.ntfp"
    )
    if linear:
        return render_4bpp_linear(texture, palette, tile_columns * 8)
    return render_4bpp(
        texture,
        palette,
        tile_columns,
        column_major=column_major,
        frame_rows=frame_rows,
    )


def available_items(archive: PackedArchive, language: str, character: str) -> list[str]:
    prefix = f"{language}\\{character}\\data_{character}_"
    return [
        name[len(prefix) : -5]
        for name in archive.names()
        if name.startswith(prefix) and name.endswith(".ntft")
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render Data Mode character OBJ tiles using several atlas widths."
    )
    parser.add_argument("character", help="three-letter Data Mode character code, e.g. gkn")
    parser.add_argument("--items", nargs="*", help="items such as ex1 sp1 team1")
    parser.add_argument("--tile-columns", type=int, nargs="+", default=(4, 8, 16, 32))
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--column-major", action="store_true")
    parser.add_argument("--frame-rows", type=int)
    parser.add_argument("--linear", action="store_true")
    parser.add_argument(
        "--combined",
        action="store_true",
        help="also create one vertically combined JA/EN sheet for the character",
    )
    parser.add_argument(
        "--split-rows",
        type=int,
        help="place this many rendered tile rows per horizontal block",
    )
    parser.add_argument(
        "--rom",
        type=Path,
        default=PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "build/data_character_layouts",
    )
    args = parser.parse_args()

    rom = NDSRom.from_file(args.rom)
    archives = {
        "JA": PackedArchive(rom.get_file(JA_PATH)),
        "EN": PackedArchive(rom.get_file(EN_PATH)),
    }
    items = args.items or available_items(archives["JA"], "JA", args.character)
    target = args.output_dir / args.character
    target.mkdir(parents=True, exist_ok=True)
    combined_rows: list[tuple[str, Image.Image]] = []

    for item in items:
        rendered: list[tuple[str, int, Image.Image]] = []
        for language, archive in archives.items():
            for columns in args.tile_columns:
                try:
                    image = render_item(
                        archive,
                        language,
                        args.character,
                        item,
                        columns,
                        column_major=args.column_major,
                        frame_rows=args.frame_rows,
                        linear=args.linear,
                    )
                except (KeyError, ValueError):
                    continue
                if args.scale != 1:
                    image = image.resize(
                        (image.width * args.scale, image.height * args.scale),
                        Image.Resampling.NEAREST,
                    )
                if args.split_rows:
                    block_height = args.split_rows * 8 * args.scale
                    blocks = [
                        image.crop((0, y, image.width, min(y + block_height, image.height)))
                        for y in range(0, image.height, block_height)
                    ]
                    rearranged = Image.new(
                        "RGBA",
                        (image.width * len(blocks), block_height),
                        BACKGROUND,
                    )
                    for block_index, block in enumerate(blocks):
                        rearranged.alpha_composite(block, (block_index * image.width, 0))
                    image = rearranged
                image.save(target / f"{item}_{language}_{columns}t.png")
                rendered.append((language, columns, image))
        if not rendered:
            continue
        cell_width = max(image.width for _, _, image in rendered) + 16
        cell_height = max(image.height for _, _, image in rendered) + 28
        sheet = Image.new("RGBA", (cell_width * len(rendered), cell_height), BACKGROUND)
        draw = ImageDraw.Draw(sheet)
        for index, (language, columns, image) in enumerate(rendered):
            x = index * cell_width
            draw.text((x + 4, 4), f"{language} / {columns} tiles", fill="white")
            sheet.alpha_composite(image, (x + 4, 24))
        output = target / f"{item}_layouts.png"
        sheet.save(output)
        combined_rows.append((item, sheet))
        print(output)

    if args.combined and combined_rows:
        label_height = 22
        combined = Image.new(
            "RGBA",
            (
                max(sheet.width for _, sheet in combined_rows),
                sum(sheet.height + label_height for _, sheet in combined_rows),
            ),
            BACKGROUND,
        )
        draw = ImageDraw.Draw(combined)
        y = 0
        for item, sheet in combined_rows:
            draw.text((4, y + 3), item, fill="white")
            combined.alpha_composite(sheet, (0, y + label_height))
            y += sheet.height + label_height
        output = target / f"{args.character}_all_JA_EN.png"
        combined.save(output)
        print(output)


if __name__ == "__main__":
    main()
