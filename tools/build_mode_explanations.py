#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.font import centered_text_block_origin
from dbzbr.nitro_bg import (
    decode_4bpp_screen,
    decode_bgr555_palette,
    encode_4bpp_screen,
)
from dbzbr.uistage import (
    add_stage_arguments,
    finish_stage,
    load_masks,
    load_stage,
    read_rows_by_id,
    write_report,
)

RESOURCE_PATH = "romdata/modeselect/ModeSelectSubScrExplanationJA.bin"
US_RESOURCE_PATH = "romdata/modeselect/ModeSelectSubScrExplanationUS.bin"
BODY_RECT = (16, 64, 240, 144)
LINE_HEIGHT = 15
FOREGROUND_INDEX = 7


def replace_body_text(
    pixels: list[list[int]], text: str, masks: dict[str, list[list[bool]]]
) -> list[list[int]]:
    output = [row[:] for row in pixels]
    x0, y0, x1, y1 = BODY_RECT
    for y in range(y0, y1):
        for x in range(x0, x1):
            output[y][x] = 0

    lines = text.split("\\n")
    line_widths = [sum(len(masks[character][0]) for character in line) for line in lines]
    block_width = max(line_widths, default=0)
    if block_width > x1 - x0:
        raise ValueError("translated explanation text block is too wide")
    glyph_height = max(
        (len(masks[character]) for line in lines for character in line), default=0
    )
    block_height = glyph_height + max(0, len(lines) - 1) * LINE_HEIGHT
    if block_height > y1 - y0:
        raise ValueError("translated explanation has too many lines")
    block_x, start_y = centered_text_block_origin(
        BODY_RECT, lines, masks, LINE_HEIGHT
    )

    for line_index, line in enumerate(lines):
        cursor_x = block_x
        cursor_y = start_y + line_index * LINE_HEIGHT
        for character in line:
            mask = masks.get(character)
            if mask is None:
                raise ValueError(f"BDF has no glyph for {character} U+{ord(character):04X}")
            width = len(mask[0]) if mask else 0
            for glyph_y, row in enumerate(mask):
                for glyph_x, foreground in enumerate(row):
                    if foreground:
                        output[cursor_y + glyph_y][cursor_x + glyph_x] = FOREGROUND_INDEX
            cursor_x += width
    return output


def indexed_image(
    pixels: list[list[int]], palette_data: bytes, *, background=(36, 39, 48, 255)
) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (256, 256), background)
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def unpack_screen(archive: PackedArchive, base: str, region: str):
    characters = archive.unpack(f"{base}_{region}.nbfc")
    palette = archive.unpack(f"{base}_{region}.nbfp")
    screen = archive.unpack(f"{base}_{region}.nbfs")
    return decode_4bpp_screen(characters, screen), palette


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized mode explanation graphics."),
        project_root=PROJECT_ROOT,
        base_rom="build/DBZ_Bukuu_Ressen_CN.nds",
        table="data/translation/ui_mode_explanations.tsv",
        output_dir="build/ui_mode_test",
    )
    parser.add_argument(
        "--entry",
        default="all",
        help="Mode id to localize, or 'all' for every mode explanation",
    )
    args = parser.parse_args()

    rows = read_rows_by_id(args.table)
    if args.entry != "all" and args.entry not in rows:
        raise ValueError(f"unknown mode explanation id: {args.entry}")
    selected_ids = list(rows) if args.entry == "all" else [args.entry]
    for entry_id in selected_ids:
        if not rows[entry_id]["simplified_chinese"]:
            raise ValueError(f"mode explanation {entry_id} has no translation")

    stage = load_stage(args, PROJECT_ROOT)
    base_rom = stage.base_rom
    source_rom = stage.source_rom

    original_resource = base_rom.get_file(RESOURCE_PATH)
    archive = PackedArchive(original_resource)
    all_characters = "".join(
        rows[entry_id]["simplified_chinese"].replace("\\n", "")
        for entry_id in selected_ids
    )
    masks = load_masks(args.bdf, all_characters)

    localized: dict[str, dict[str, object]] = {}
    for entry_id in selected_ids:
        translation = rows[entry_id]["simplified_chinese"]
        original_pixels, palette = unpack_screen(archive, entry_id, "JA")
        localized_pixels = replace_body_text(original_pixels, translation, masks)
        characters, screen = encode_4bpp_screen(localized_pixels)
        archive.replace_unpacked(f"{entry_id}_JA.nbfc", characters)
        archive.replace_unpacked(f"{entry_id}_JA.nbfs", screen)
        localized[entry_id] = {
            "pixels": localized_pixels,
            "palette": palette,
            "character_tiles": len(characters) // 32,
        }
    rebuilt_resource = archive.build()

    output_stem = (
        "DBZ_Bukuu_Ressen_CN_AllModeExplanationsTest"
        if args.entry == "all"
        else f"DBZ_Bukuu_Ressen_CN_{args.entry}_ModeExplanationTest"
    )
    result = finish_stage(
        stage,
        {RESOURCE_PATH: rebuilt_resource},
        rom_name=output_stem,
        metadata=b"DBZ BR CN mode explanation test",
        resource_names={RESOURCE_PATH: "ModeSelectSubScrExplanationJA_CN.bin"},
    )
    output_bytes = result.output_bytes

    rebuilt_archive = PackedArchive(rebuilt_resource)
    for entry_id in selected_ids:
        decoded_pixels, rebuilt_palette = unpack_screen(rebuilt_archive, entry_id, "JA")
        if (
            decoded_pixels != localized[entry_id]["pixels"]
            or rebuilt_palette != localized[entry_id]["palette"]
        ):
            raise ValueError(f"rebuilt mode explanation failed decode validation: {entry_id}")

    changed_rom_files = result.changed_from_base

    original_archive_check = PackedArchive(original_resource)
    changed_archive_entries = []
    for index, (before, after) in enumerate(
        zip(original_archive_check.entries, rebuilt_archive.entries)
    ):
        before_data = original_archive_check.decompress(before.packed_data)
        after_data = rebuilt_archive.decompress(after.packed_data)
        if before_data != after_data:
            changed_archive_entries.append({"index": index, "name": before.name})
    changed_names = {
        f"{entry_id}_JA.{extension}"
        for entry_id in selected_ids
        for extension in ("nbfc", "nbfs")
    }
    if {item["name"] for item in changed_archive_entries} != changed_names:
        raise ValueError(f"unexpected changed packed entries: {changed_archive_entries}")

    source_ja = PackedArchive(source_rom.get_file(RESOURCE_PATH))
    source_us = PackedArchive(source_rom.get_file(US_RESOURCE_PATH))
    preview_path = args.output_dir / (
        "all_JA_US_CN.png" if args.entry == "all" else f"{args.entry}_JA_US_CN.png"
    )
    sheet = Image.new(
        "RGBA", (768, len(selected_ids) * 280), (36, 39, 48, 255)
    )
    sheet_draw = ImageDraw.Draw(sheet)
    preview_paths: dict[str, str] = {}
    for row_index, entry_id in enumerate(selected_ids):
        ja_pixels, ja_palette = unpack_screen(source_ja, entry_id, "JA")
        us_pixels, us_palette = unpack_screen(source_us, entry_id, "US")
        previews = {
            "JA": indexed_image(ja_pixels, ja_palette),
            "US": indexed_image(us_pixels, us_palette),
            "CN": indexed_image(
                localized[entry_id]["pixels"], localized[entry_id]["palette"]
            ),
        }
        for label, preview in previews.items():
            preview.save(args.output_dir / f"{entry_id}_{label}.png")
        entry_sheet = Image.new("RGBA", (768, 280), (36, 39, 48, 255))
        entry_draw = ImageDraw.Draw(entry_sheet)
        for column, label in enumerate(("JA", "US", "CN")):
            entry_draw.text(
                (column * 256 + 4, 2),
                f"{entry_id} / {label}",
                fill=(255, 255, 255, 255),
            )
            entry_sheet.alpha_composite(previews[label], (column * 256, 20))
            sheet_draw.text(
                (column * 256 + 4, row_index * 280 + 2),
                f"{entry_id} / {label}",
                fill=(255, 255, 255, 255),
            )
            sheet.alpha_composite(previews[label], (column * 256, row_index * 280 + 20))
        entry_preview_path = args.output_dir / f"{entry_id}_JA_US_CN.png"
        entry_sheet.save(entry_preview_path)
        preview_paths[entry_id] = str(entry_preview_path)
    sheet.save(preview_path)

    unchanged_entry_names = []
    for name in sorted(set(archive.names()) - changed_names):
        if original_archive_check.unpack(name) != rebuilt_archive.unpack(name):
            raise ValueError(f"unexpected changed archive entry: {name}")
        unchanged_entry_names.append(name)

    report = {
        "selection": args.entry,
        "entries": [
            {
                "id": entry_id,
                "title_art": "preserved original graphic",
                "translation": rows[entry_id]["simplified_chinese"],
                "localized_character_tiles": localized[entry_id]["character_tiles"],
                "preview": preview_paths[entry_id],
            }
            for entry_id in selected_ids
        ],
        "font_bdf": str(args.bdf),
        "layout": {
            "body_rect": BODY_RECT,
            "line_height": LINE_HEIGHT,
            "horizontal_alignment": "left within centered text block",
            "vertical_alignment": "center",
        },
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "original_resource_size": len(original_resource),
        "rebuilt_resource_size": len(rebuilt_resource),
        "unchanged_unique_archive_entries": len(unchanged_entry_names),
        "changed_repeated_archive_entries": changed_archive_entries,
        "changed_rom_files": changed_rom_files,
        "resource_rom_range": [result.replaced[0].start, result.replaced[0].end],
        "output_rom": str(result.rom_path),
        "output_patch": str(result.patch_path),
        "preview": str(preview_path),
    }
    write_report(stage, report, "build_report.json")


if __name__ == "__main__":
    main()
