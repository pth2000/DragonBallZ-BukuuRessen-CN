#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.font import centered_text_block_origin
from dbzbr.nitro_bg import decode_4bpp_screen, encode_4bpp_screen
from dbzbr.uistage import (
    PREVIEW_BACKGROUND,
    add_stage_arguments,
    changed_entries,
    finish_stage,
    indexed_image,
    load_stage,
    read_rows_by_id,
    write_report,
)

RESOURCE_PATH = "romdata/scene/common/maxselect.bin"
ENTRY_IDS = ("doc00", "doc01", "doc02")
BODY_RECT = (24, 80, 232, 128)
LINE_HEIGHT = 15
FOREGROUND_INDEX = 7


def unpack_screen(
    archive: PackedArchive, entry_id: str, language: str
) -> tuple[list[list[int]], bytes]:
    stem = f"max_{language}_{entry_id}"
    characters = archive.unpack(f"{stem}.nbfc")
    screen = archive.unpack(f"{stem}.nbfs")
    palette = archive.unpack(f"max_{language}_doc00.nbfp")
    return decode_4bpp_screen(characters, screen), palette


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
        raise ValueError(f"MAXIMUM explanation is too wide: {text}")
    if block_height > y1 - y0:
        raise ValueError(f"MAXIMUM explanation is too tall: {text}")

    start_x, start_y = centered_text_block_origin(
        BODY_RECT, lines, masks, LINE_HEIGHT
    )
    for line_index, line in enumerate(lines):
        cursor_x = start_x
        cursor_y = start_y + line_index * LINE_HEIGHT
        for character in line:
            mask = masks[character]
            for glyph_y, row in enumerate(mask):
                for glyph_x, foreground in enumerate(row):
                    if foreground:
                        output[cursor_y + glyph_y][cursor_x + glyph_x] = FOREGROUND_INDEX
            cursor_x += len(mask[0])
    return output


def assert_unchanged_outside_body(
    before: list[list[int]], after: list[list[int]], entry_id: str
) -> None:
    x0, y0, x1, y1 = BODY_RECT
    for y, (before_row, after_row) in enumerate(zip(before, after)):
        for x, (old, new) in enumerate(zip(before_row, after_row)):
            if old != new and not (x0 <= x < x1 and y0 <= y < y1):
                raise ValueError(f"pixel outside body changed: {entry_id} at {x},{y}")


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized MAXIMUM rank explanations."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_clear_test/DBZ_Bukuu_Ressen_CN_UI_ClearTest.nds",
        table="data/translation/ui_maximum_explanations.tsv",
        output_dir="build/ui_maximum_test",
    )
    args = parser.parse_args()

    rows = read_rows_by_id(args.table)
    if tuple(rows) != ENTRY_IDS:
        raise ValueError(f"expected MAXIMUM rows {ENTRY_IDS}, got {tuple(rows)}")
    translations = {entry_id: rows[entry_id]["simplified_chinese"] for entry_id in ENTRY_IDS}
    if any(not text for text in translations.values()):
        raise ValueError("every MAXIMUM rank explanation requires a translation")
    all_characters = "".join(text.replace("\\n", "") for text in translations.values())

    stage = load_stage(args, PROJECT_ROOT, characters=all_characters)
    masks = stage.masks
    original_data = stage.base_rom.get_file(RESOURCE_PATH)
    original = PackedArchive(original_data)
    archive = PackedArchive(original_data)

    localized: dict[str, dict[str, object]] = {}
    for entry_id in ENTRY_IDS:
        before, palette = unpack_screen(original, entry_id, "jp")
        after = replace_text_block(before, translations[entry_id], masks)
        assert_unchanged_outside_body(before, after, entry_id)
        characters, screen = encode_4bpp_screen(after)
        archive.replace_unpacked(f"max_jp_{entry_id}.nbfc", characters)
        archive.replace_unpacked(f"max_jp_{entry_id}.nbfs", screen)
        localized[entry_id] = {
            "before": before,
            "after": after,
            "palette": palette,
            "character_tiles": len(characters) // 32,
        }

    rebuilt_data = archive.build()
    rebuilt = PackedArchive(rebuilt_data)
    for entry_id in ENTRY_IDS:
        pixels, palette = unpack_screen(rebuilt, entry_id, "jp")
        if pixels != localized[entry_id]["after"] or palette != localized[entry_id]["palette"]:
            raise ValueError(f"rebuilt MAXIMUM screen failed validation: {entry_id}")
    expected_changes = {
        f"max_jp_{entry_id}.{extension}"
        for entry_id in ENTRY_IDS
        for extension in ("nbfc", "nbfs")
    }
    actual_changes = set(changed_entries(original, rebuilt))
    if actual_changes != expected_changes:
        raise ValueError(f"unexpected MAXIMUM archive changes: {actual_changes ^ expected_changes}")

    result = finish_stage(
        stage,
        {RESOURCE_PATH: rebuilt_data},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_MaximumTest",
        metadata=b"DBZ BR CN MAXIMUM explanations",
        resource_names={RESOURCE_PATH: "maxselect_CN.bin"},
    )

    source_archive = stage.source_resource(RESOURCE_PATH)
    sheet = Image.new("RGBA", (768, len(ENTRY_IDS) * 212), PREVIEW_BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    preview_paths = {}
    for row_index, entry_id in enumerate(ENTRY_IDS):
        jp_pixels, jp_palette = unpack_screen(source_archive, entry_id, "jp")
        en_pixels, en_palette = unpack_screen(source_archive, entry_id, "en")
        images = {
            "JP": indexed_image(jp_pixels, jp_palette),
            "US": indexed_image(en_pixels, en_palette),
            "CN": indexed_image(localized[entry_id]["after"], localized[entry_id]["palette"]),
        }
        entry_sheet = Image.new("RGBA", (768, 212), PREVIEW_BACKGROUND)
        entry_draw = ImageDraw.Draw(entry_sheet)
        for column, label in enumerate(("JP", "US", "CN")):
            x = column * 256
            y = row_index * 212
            entry_draw.text((x + 4, 2), f"{entry_id} / {label}", fill="white")
            entry_sheet.alpha_composite(images[label], (x, 20))
            draw.text((x + 4, y + 2), f"{entry_id} / {label}", fill="white")
            sheet.alpha_composite(images[label], (x, y + 20))
        entry_path = args.output_dir / f"{entry_id}_JP_US_CN.png"
        entry_sheet.save(entry_path)
        preview_paths[entry_id] = str(entry_path)
    preview_path = args.output_dir / "all_JP_US_CN.png"
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
            for entry_id in ENTRY_IDS
        ],
        "style_policy": "localized functional body text; preserved stylized rank titles",
        "layout": {
            "body_rect": BODY_RECT,
            "line_height": LINE_HEIGHT,
            "horizontal_alignment": "left within centered text block",
            "vertical_alignment": "center",
        },
        **result.report_fields(stage.base_bytes, args.bdf),
        "changed_archive_entries": sorted(actual_changes),
        "preview": str(preview_path),
    }
    write_report(stage, report)


if __name__ == "__main__":
    main()
