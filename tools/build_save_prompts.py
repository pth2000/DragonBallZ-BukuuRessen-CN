#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nitro_bg import decode_4bpp_screen, decode_bgr555_palette, encode_4bpp_screen
from dbzbr.uistage import (
    PREVIEW_BACKGROUND,
    add_stage_arguments,
    finish_stage,
    load_stage,
    write_report,
)

RESOURCE_PATH = "romdata/opening/OpnSaveLoadJA.bin"
US_RESOURCE_PATH = "romdata/opening/OpnSaveLoadUS.bin"
STEM = "SaveDamage4JP"
TEXT_RECT = (40, 72, 220, 122)
BACKGROUND_INDEX = 4
TEXT_INDEX = 1
LINE_HEIGHT = 22


def read_translation(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 1 or rows[0]["id"] != "save_damage":
        raise ValueError("save prompt table must contain exactly the save_damage row")
    return rows[0]["simplified_chinese"]


def draw_line(
    pixels: list[list[int]],
    line: str,
    masks: dict[str, list[list[bool]]],
    x: int,
    y: int,
) -> None:
    cursor_x = x
    for character in line:
        mask = masks[character]
        for glyph_y, row in enumerate(mask):
            for glyph_x, foreground in enumerate(row):
                if foreground:
                    pixels[y + glyph_y][cursor_x + glyph_x] = TEXT_INDEX
        cursor_x += len(mask[0])


def replace_prompt(
    pixels: list[list[int]], text: str, masks: dict[str, list[list[bool]]]
) -> list[list[int]]:
    output = [row[:] for row in pixels]
    x0, y0, x1, y1 = TEXT_RECT
    for y in range(y0, y1):
        for x in range(x0, x1):
            output[y][x] = BACKGROUND_INDEX
    lines = text.split("\\n")
    widths = [sum(len(masks[character][0]) for character in line) for line in lines]
    block_width = max(widths, default=0)
    glyph_height = max(
        (len(masks[character]) for line in lines for character in line), default=0
    )
    block_height = glyph_height + max(0, len(lines) - 1) * LINE_HEIGHT
    if block_width > x1 - x0 or block_height > y1 - y0:
        raise ValueError("save prompt does not fit")
    block_x = x0 + (x1 - x0 - block_width) // 2
    start_y = y0 + (y1 - y0 - block_height) // 2
    for line_index, line in enumerate(lines):
        draw_line(output, line, masks, block_x, start_y + line_index * LINE_HEIGHT)
    return output


def unpack_screen(archive: PackedArchive, stem: str) -> tuple[list[list[int]], bytes]:
    return (
        decode_4bpp_screen(archive.unpack(f"{stem}.nbfc"), archive.unpack(f"{stem}.nbfs")),
        archive.unpack(f"{stem}.nbfp"),
    )


def render(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (256, len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized corrupted-save prompt."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_data_test/DBZ_Bukuu_Ressen_CN_UI_DataTest.nds",
        table="data/translation/ui_save_prompts.tsv",
        output_dir="build/ui_save_test",
    )
    args = parser.parse_args()

    translation = read_translation(args.table)
    characters = translation.replace("\\n", "")

    stage = load_stage(args, PROJECT_ROOT, characters=characters)
    masks = stage.masks
    source_rom = stage.source_rom
    original_resource = stage.base_rom.get_file(RESOURCE_PATH)
    original_archive = PackedArchive(original_resource)
    archive = PackedArchive(original_resource)
    original_pixels, palette = unpack_screen(archive, STEM)
    localized_pixels = replace_prompt(original_pixels, translation, masks)
    characters_data, screen_data = encode_4bpp_screen(localized_pixels)
    archive.replace_unpacked(f"{STEM}.nbfc", characters_data)
    archive.replace_unpacked(f"{STEM}.nbfs", screen_data)
    rebuilt_resource = archive.build()

    result = finish_stage(
        stage,
        {RESOURCE_PATH: rebuilt_resource},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_SaveTest",
        metadata=b"DBZ BR CN save prompt",
        resource_names={RESOURCE_PATH: "OpnSaveLoadJA_CN.bin"},
    )

    rebuilt_archive = PackedArchive(rebuilt_resource)
    decoded_pixels, rebuilt_palette = unpack_screen(rebuilt_archive, STEM)
    if decoded_pixels != localized_pixels or rebuilt_palette != palette:
        raise ValueError("rebuilt save prompt failed validation")
    changes = [
        {"index": index, "name": before.name}
        for index, (before, after) in enumerate(zip(original_archive.entries, rebuilt_archive.entries))
        if original_archive.decompress(before.packed_data)
        != rebuilt_archive.decompress(after.packed_data)
    ]
    if {item["name"] for item in changes} != {f"{STEM}.nbfc", f"{STEM}.nbfs"}:
        raise ValueError(f"unexpected save archive changes: {changes}")

    source_jp = PackedArchive(source_rom.get_file(RESOURCE_PATH))
    source_us = PackedArchive(source_rom.get_file(US_RESOURCE_PATH))
    jp_pixels, jp_palette = unpack_screen(source_jp, STEM)
    us_pixels, us_palette = unpack_screen(source_us, STEM)
    previews = {
        "JP": render(jp_pixels, jp_palette),
        "US": render(us_pixels, us_palette),
        "CN": render(localized_pixels, palette),
    }
    sheet = Image.new("RGBA", (768, 276), PREVIEW_BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    for column, label in enumerate(("JP", "US", "CN")):
        draw.text((column * 256 + 4, 2), f"save damage / {label}", fill="white")
        sheet.alpha_composite(previews[label], (column * 256, 20))
    preview_path = args.output_dir / "save_damage_JP_US_CN.png"
    sheet.save(preview_path)

    report = {
        "translation": translation,
        "style_policy": "localized Japanese system text; preserved window artwork",
        "text_rect": TEXT_RECT,
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(result.output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "changed_from_base": result.changed_from_base,
        "changed_from_source": result.changed_from_source,
        "changed_archive_entries": changes,
        "resource_rom_range": [result.replaced[0].start, result.replaced[0].end],
        "output_rom": str(result.rom_path),
        "output_patch": str(result.patch_path),
        "preview": str(preview_path),
    }
    write_report(stage, report, "build_report.json")


if __name__ == "__main__":
    main()
