#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib

from _bootstrap import PROJECT_ROOT
from build_mode_explanations import indexed_image
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.font import centered_text_block_origin
from dbzbr.nitro_bg import decode_4bpp_screen, encode_4bpp_screen
from dbzbr.uistage import (
    add_stage_arguments,
    finish_stage,
    load_stage,
    read_rows_by_id,
    write_report,
)

RESOURCE_PATH = "romdata/stageselect/StageSelectSubScrBGJA.bin"
US_RESOURCE_PATH = "romdata/stageselect/StageSelectSubScrBGUS.bin"
TITLE_RECT = (0, 16, 256, 48)
# All 16 original JP descriptions share a y=104 visual center.  In-game BG
# composition places this seven pixels above the old geometric assumption.
BODY_RECT = (0, 65, 256, 145)
LINE_HEIGHT = 15
TITLE_INDEX = 4
BODY_INDEX = 1
TITLE_Y_ADJUST = 1


def unpack_screen(archive: PackedArchive, entry_id: str, region: str):
    base = f"{entry_id}{region}"
    characters = archive.unpack(f"{base}.nbfc")
    palette = archive.unpack(f"{base}.nbfp")
    screen = archive.unpack(f"{base}.nbfs")
    return decode_4bpp_screen(characters, screen), palette


def clear_rect(pixels: list[list[int]], rect: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            pixels[y][x] = 0


def draw_line(
    pixels: list[list[int]],
    line: str,
    masks: dict[str, list[list[bool]]],
    x: int,
    y: int,
    color_index: int,
) -> None:
    cursor_x = x
    for character in line:
        mask = masks[character]
        for glyph_y, row in enumerate(mask):
            for glyph_x, foreground in enumerate(row):
                if foreground:
                    pixels[y + glyph_y][cursor_x + glyph_x] = color_index
        cursor_x += len(mask[0])


def replace_stage_text(
    pixels: list[list[int]],
    title: str,
    description: str,
    masks: dict[str, list[list[bool]]],
) -> list[list[int]]:
    output = [row[:] for row in pixels]
    clear_rect(output, TITLE_RECT)
    clear_rect(output, BODY_RECT)

    title_width = sum(len(masks[character][0]) for character in title)
    if title_width > TITLE_RECT[2] - 8:
        raise ValueError(f"stage title is too wide: {title}")
    _, title_y = centered_text_block_origin(
        TITLE_RECT, [title], masks, LINE_HEIGHT
    )
    # Original JP title ink is centered at y=32; the 11px Chinese ink box
    # otherwise lands at y=31 because of integer centering in the 32px strip.
    title_y += TITLE_Y_ADJUST
    draw_line(output, title, masks, 4, title_y, TITLE_INDEX)

    lines = description.split("\\n")
    widths = [sum(len(masks[character][0]) for character in line) for line in lines]
    block_width = max(widths, default=0)
    glyph_height = max(
        (len(masks[character]) for line in lines for character in line), default=0
    )
    block_height = glyph_height + max(0, len(lines) - 1) * LINE_HEIGHT
    x0, y0, x1, y1 = BODY_RECT
    if block_width > x1 - x0:
        raise ValueError(f"stage description is too wide: {title}")
    if block_height > y1 - y0:
        raise ValueError(f"stage description is too tall: {title}")
    block_x, start_y = centered_text_block_origin(
        BODY_RECT, lines, masks, LINE_HEIGHT
    )
    for line_index, line in enumerate(lines):
        draw_line(
            output,
            line,
            masks,
            block_x,
            start_y + line_index * LINE_HEIGHT,
            BODY_INDEX,
        )
    return output


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized stage names and explanations."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_option_test/DBZ_Bukuu_Ressen_CN_UI_ExplanationsTest.nds",
        table="data/translation/ui_stage_explanations.tsv",
        output_dir="build/ui_stage_test",
    )
    args = parser.parse_args()

    rows = read_rows_by_id(args.table)
    entry_ids = list(rows)
    all_characters = "".join(
        rows[entry_id][field].replace("\\n", "")
        for entry_id in entry_ids
        for field in ("title_chinese", "description_chinese")
    )
    stage = load_stage(args, PROJECT_ROOT, characters=all_characters)
    masks = stage.masks
    source_rom = stage.source_rom

    original_resource = stage.base_rom.get_file(RESOURCE_PATH)
    archive = PackedArchive(original_resource)
    localized: dict[str, dict[str, object]] = {}
    for entry_id in entry_ids:
        original_pixels, palette = unpack_screen(archive, entry_id, "JA")
        pixels = replace_stage_text(
            original_pixels,
            rows[entry_id]["title_chinese"],
            rows[entry_id]["description_chinese"],
            masks,
        )
        characters, screen = encode_4bpp_screen(pixels)
        archive.replace_unpacked(f"{entry_id}JA.nbfc", characters)
        archive.replace_unpacked(f"{entry_id}JA.nbfs", screen)
        localized[entry_id] = {
            "pixels": pixels,
            "palette": palette,
            "character_tiles": len(characters) // 32,
        }
    rebuilt_resource = archive.build()

    result = finish_stage(
        stage,
        {RESOURCE_PATH: rebuilt_resource},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_StageTest",
        metadata=b"DBZ BR CN stage UI test",
        resource_names={RESOURCE_PATH: "StageSelectSubScrBGJA_CN.bin"},
    )
    output_bytes = result.output_bytes

    rebuilt_archive = PackedArchive(rebuilt_resource)
    for entry_id in entry_ids:
        pixels, palette = unpack_screen(rebuilt_archive, entry_id, "JA")
        if pixels != localized[entry_id]["pixels"] or palette != localized[entry_id]["palette"]:
            raise ValueError(f"rebuilt stage screen failed validation: {entry_id}")

    changed_rom_files = result.changed_from_base

    original_archive = PackedArchive(original_resource)
    changed_entries = []
    for index, (before, after) in enumerate(zip(original_archive.entries, rebuilt_archive.entries)):
        if original_archive.decompress(before.packed_data) != rebuilt_archive.decompress(after.packed_data):
            changed_entries.append({"index": index, "name": before.name})
    changed_names = {
        f"{entry_id}JA.{extension}"
        for entry_id in entry_ids
        for extension in ("nbfc", "nbfs")
    }
    if {item["name"] for item in changed_entries} != changed_names:
        raise ValueError(f"unexpected changed packed entries: {changed_entries}")

    source_ja = PackedArchive(source_rom.get_file(RESOURCE_PATH))
    source_us = PackedArchive(source_rom.get_file(US_RESOURCE_PATH))
    sheet = Image.new("RGBA", (768, len(entry_ids) * 280), (36, 39, 48, 255))
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
        entry_sheet = Image.new("RGBA", (768, 280), (36, 39, 48, 255))
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
                "title": rows[entry_id]["title_chinese"],
                "description": rows[entry_id]["description_chinese"],
                "localized_character_tiles": localized[entry_id]["character_tiles"],
                "preview": preview_paths[entry_id],
            }
            for entry_id in entry_ids
        ],
        "layout": {
            "title_rect": TITLE_RECT,
            "body_rect": BODY_RECT,
            "line_height": LINE_HEIGHT,
            "title_alignment": "left",
            "body_alignment": "left within centered text block",
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
    write_report(stage, report, "build_report.json")


if __name__ == "__main__":
    main()
