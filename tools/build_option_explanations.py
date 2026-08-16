#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json

from _bootstrap import PROJECT_ROOT
from build_mode_explanations import unpack_screen
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.font import centered_text_block_origin
from dbzbr.nitro_bg import encode_4bpp_screen
from dbzbr.uistage import (
    PREVIEW_BACKGROUND,
    add_stage_arguments,
    finish_stage,
    indexed_image,
    load_stage,
    read_rows_by_id,
)

RESOURCE_PATH = "romdata/option/OptSubTxtJA.bin"
US_RESOURCE_PATH = "romdata/option/OptSubTxtUS.bin"
# The original JP explanation ink is centered around y=103.  The background
# tilemap is shifted when composited in-game, so the apparent panel center is
# four pixels above the previously assumed rectangle.
BODY_RECT = (16, 68, 240, 140)
LINE_HEIGHT = 15
FOREGROUND_INDEX = 7


def replace_text_block(
    pixels: list[list[int]], text: str, masks: dict[str, list[list[bool]]]
) -> list[list[int]]:
    output = [row[:] for row in pixels]
    x0, y0, x1, y1 = BODY_RECT
    for y in range(y0, y1):
        for x in range(x0, x1):
            output[y][x] = 0

    lines = text.split("\\n")
    widths = [sum(len(masks[character][0]) for character in line) for line in lines]
    block_width = max(widths, default=0)
    glyph_height = max(
        (len(masks[character]) for line in lines for character in line), default=0
    )
    block_height = glyph_height + max(0, len(lines) - 1) * LINE_HEIGHT
    if block_width > x1 - x0:
        raise ValueError("translated option text block is too wide")
    if block_height > y1 - y0:
        raise ValueError("translated option text block is too tall")
    block_x, start_y = centered_text_block_origin(
        BODY_RECT, lines, masks, LINE_HEIGHT
    )

    for line_index, line in enumerate(lines):
        cursor_x = block_x
        cursor_y = start_y + line_index * LINE_HEIGHT
        for character in line:
            mask = masks[character]
            for glyph_y, row in enumerate(mask):
                for glyph_x, foreground in enumerate(row):
                    if foreground:
                        output[cursor_y + glyph_y][cursor_x + glyph_x] = FOREGROUND_INDEX
            cursor_x += len(mask[0])
    return output


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized option explanation graphics."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_mode_test/DBZ_Bukuu_Ressen_CN_AllModeExplanationsTest.nds",
        table="data/translation/ui_option_explanations.tsv",
        output_dir="build/ui_option_test",
    )
    args = parser.parse_args()

    rows = read_rows_by_id(args.table)
    entry_ids = list(rows)
    translations = {entry_id: rows[entry_id]["simplified_chinese"] for entry_id in entry_ids}
    if any(not text for text in translations.values()):
        raise ValueError("every option explanation requires a translation")
    all_characters = "".join(text.replace("\\n", "") for text in translations.values())

    stage = load_stage(args, PROJECT_ROOT, characters=all_characters)
    masks = stage.masks
    base_rom = stage.base_rom
    source_rom = stage.source_rom

    original_resource = base_rom.get_file(RESOURCE_PATH)
    archive = PackedArchive(original_resource)
    localized: dict[str, dict[str, object]] = {}
    for entry_id in entry_ids:
        original_pixels, palette = unpack_screen(archive, entry_id, "JA")
        pixels = replace_text_block(original_pixels, translations[entry_id], masks)
        characters, screen = encode_4bpp_screen(pixels)
        archive.replace_unpacked(f"{entry_id}_JA.nbfc", characters)
        archive.replace_unpacked(f"{entry_id}_JA.nbfs", screen)
        localized[entry_id] = {
            "pixels": pixels,
            "palette": palette,
            "character_tiles": len(characters) // 32,
        }
    rebuilt_resource = archive.build()

    result = finish_stage(
        stage,
        {RESOURCE_PATH: rebuilt_resource},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_ExplanationsTest",
        metadata=b"DBZ BR CN UI explanation test",
        resource_names={RESOURCE_PATH: "OptSubTxtJA_CN.bin"},
    )
    output_bytes = result.output_bytes

    rebuilt_archive = PackedArchive(rebuilt_resource)
    for entry_id in entry_ids:
        pixels, palette = unpack_screen(rebuilt_archive, entry_id, "JA")
        if pixels != localized[entry_id]["pixels"] or palette != localized[entry_id]["palette"]:
            raise ValueError(f"rebuilt option explanation failed validation: {entry_id}")

    changed_rom_files = result.changed_from_base

    original_archive = PackedArchive(original_resource)
    changed_entries = []
    for index, (before, after) in enumerate(zip(original_archive.entries, rebuilt_archive.entries)):
        if original_archive.decompress(before.packed_data) != rebuilt_archive.decompress(after.packed_data):
            changed_entries.append({"index": index, "name": before.name})
    changed_names = {
        f"{entry_id}_JA.{extension}"
        for entry_id in entry_ids
        for extension in ("nbfc", "nbfs")
    }
    if {item["name"] for item in changed_entries} != changed_names:
        raise ValueError(f"unexpected changed packed entries: {changed_entries}")

    source_ja = PackedArchive(source_rom.get_file(RESOURCE_PATH))
    source_us = PackedArchive(source_rom.get_file(US_RESOURCE_PATH))
    sheet = Image.new("RGBA", (768, len(entry_ids) * 280), PREVIEW_BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    preview_paths = {}
    for row_index, entry_id in enumerate(entry_ids):
        ja_pixels, ja_palette = unpack_screen(source_ja, entry_id, "JA")
        us_pixels, us_palette = unpack_screen(source_us, entry_id, "US")
        previews = {
            "JA": indexed_image(ja_pixels, ja_palette),
            "US": indexed_image(us_pixels, us_palette),
            "CN": indexed_image(localized[entry_id]["pixels"], localized[entry_id]["palette"]),
        }
        entry_sheet = Image.new("RGBA", (768, 280), PREVIEW_BACKGROUND)
        entry_draw = ImageDraw.Draw(entry_sheet)
        for column, label in enumerate(("JA", "US", "CN")):
            caption = f"{entry_id} / {label}"
            entry_draw.text((column * 256 + 4, 2), caption, fill="white")
            entry_sheet.alpha_composite(previews[label], (column * 256, 20))
            draw.text((column * 256 + 4, row_index * 280 + 2), caption, fill="white")
            sheet.alpha_composite(previews[label], (column * 256, row_index * 280 + 20))
        entry_path = args.output_dir / f"{entry_id}_JA_US_CN.png"
        entry_sheet.save(entry_path)
        preview_paths[entry_id] = str(entry_path)
    preview_path = args.output_dir / "all_JA_US_CN.png"
    sheet.save(preview_path)

    report = {
        "entries": [
            {
                "id": entry_id,
                "title_art": "preserved original graphic",
                "translation": translations[entry_id],
                "localized_character_tiles": localized[entry_id]["character_tiles"],
                "preview": preview_paths[entry_id],
            }
            for entry_id in entry_ids
        ],
        "layout": {
            "body_rect": BODY_RECT,
            "line_height": LINE_HEIGHT,
            "horizontal_alignment": "left within centered text block",
            "vertical_alignment": "center",
        },
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "changed_repeated_archive_entries": changed_entries,
        "changed_rom_files": changed_rom_files,
        "resource_rom_range": [result.replaced[0].start, result.replaced[0].end],
        "output_rom": str(result.rom_path),
        "output_patch": str(result.patch_path),
        "preview": str(preview_path),
    }
    (args.output_dir / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
