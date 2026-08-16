#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nitro_bg import (
    decode_4bpp_screen,
    decode_bgr555_palette,
    encode_4bpp_screen,
)
from dbzbr.uistage import (
    PREVIEW_BACKGROUND,
    add_stage_arguments,
    finish_stage,
    load_stage,
    write_report,
)

RESOURCE_PATH = "romdata/scene/common/cstatus_bg.bin"
ROUTES = (
    "gok",
    "goh",
    "crr",
    "pic",
    "veg",
    "trk",
    "gtk",
    "gnu",
    "frz",
    "drg",
    "egh",
    "cel",
    "bmr",
    "col",
    "brl",
)
EXPECTED_COUNTS = {
    "gok": 7,
    "goh": 8,
    "crr": 5,
    "pic": 5,
    "veg": 5,
    "trk": 6,
    "gtk": 5,
    "gnu": 4,
    "frz": 5,
    "drg": 3,
    "egh": 3,
    "cel": 6,
    "bmr": 7,
    "col": 5,
    "brl": 2,
}
SLOT_TOP = 40
SLOT_HEIGHT = 16
TEXT_CLEAR_RECT = (106, 0, 255, 15)
TEXT_X = 107
TEXT_Y_OFFSET = 1
FOREGROUND_INDEX = 15
UNLOCKED_BACKGROUND_INDEX = 8


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def unpack_screen(
    archive: PackedArchive, route: str, language: str
) -> tuple[list[list[int]], bytes]:
    stem = f"cstat_{language}_{route}"
    return (
        decode_4bpp_screen(
            archive.unpack(f"{stem}.nbfc"), archive.unpack(f"{stem}.nbfs")
        ),
        archive.unpack(f"{stem}.nbfp"),
    )


def slot_rect(slot: int) -> tuple[int, int, int, int]:
    x0, _, x1, height = TEXT_CLEAR_RECT
    y0 = SLOT_TOP + slot * SLOT_HEIGHT
    return x0, y0, x1, y0 + height


def replace_move_names(
    pixels: list[list[int]],
    rows: list[dict[str, str]],
    masks: dict[str, list[list[bool]]],
) -> list[list[int]]:
    output = [row[:] for row in pixels]
    for row in rows:
        slot = int(row["slot"])
        text = row["simplified_chinese"]
        x0, y0, x1, y1 = slot_rect(slot)
        if pixels[y0 + 5][254] != UNLOCKED_BACKGROUND_INDEX:
            raise ValueError(f"slot {slot} is not an unlocked status row")
        for y in range(y0, y1):
            for x in range(x0, x1):
                output[y][x] = UNLOCKED_BACKGROUND_INDEX

        width = sum(len(masks[character][0]) for character in text)
        if width > x1 - TEXT_X:
            raise ValueError(f"status move is too wide ({width}px): {text}")
        cursor_x = TEXT_X
        cursor_y = y0 + TEXT_Y_OFFSET
        for character in text:
            mask = masks[character]
            for glyph_y, mask_row in enumerate(mask):
                for glyph_x, foreground in enumerate(mask_row):
                    if foreground:
                        output[cursor_y + glyph_y][cursor_x + glyph_x] = FOREGROUND_INDEX
            cursor_x += len(mask[0])
    return output


def assert_unchanged_outside_slots(
    before: list[list[int]],
    after: list[list[int]],
    slots: set[int],
    route: str,
) -> None:
    rects = [slot_rect(slot) for slot in slots]
    for y, (before_row, after_row) in enumerate(zip(before, after)):
        for x, (old, new) in enumerate(zip(before_row, after_row)):
            if old == new:
                continue
            if not any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in rects):
                raise ValueError(f"pixel outside status text changed: {route} at {x},{y}")


def indexed_image(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (len(pixels[0]), len(pixels)), PREVIEW_BACKGROUND)
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def changed_entries(before: PackedArchive, after: PackedArchive) -> list[str]:
    if before.names() != after.names():
        raise ValueError("character-status archive entry order changed")
    return [
        old.name
        for old, new in zip(before.entries, after.entries)
        if before.decompress(old.packed_data) != after.decompress(new.packed_data)
    ]


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized character-status move lists."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_maximum_test/DBZ_Bukuu_Ressen_CN_UI_MaximumTest.nds",
        table="data/translation/ui_character_status_moves.tsv",
        output_dir="build/ui_character_status_test",
    )
    args = parser.parse_args()

    rows = read_rows(args.table)
    by_route: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_route[row["route"]].append(row)
    if tuple(by_route) != ROUTES:
        raise ValueError(f"unexpected status routes: {tuple(by_route)}")
    for route in ROUTES:
        route_rows = by_route[route]
        expected_slots = list(range(EXPECTED_COUNTS[route]))
        actual_slots = [int(row["slot"]) for row in route_rows]
        if actual_slots != expected_slots:
            raise ValueError(f"unexpected slots for {route}: {actual_slots}")
        if any(not row["simplified_chinese"] for row in route_rows):
            raise ValueError(f"missing status translation for {route}")
    if len(rows) != sum(EXPECTED_COUNTS.values()):
        raise ValueError("character-status row count mismatch")

    all_characters = "".join(row["simplified_chinese"] for row in rows)
    stage = load_stage(args, PROJECT_ROOT, characters=all_characters)
    masks = stage.masks
    source_rom = stage.source_rom
    original_data = stage.base_rom.get_file(RESOURCE_PATH)
    original = PackedArchive(original_data)
    archive = PackedArchive(original_data)

    localized: dict[str, dict[str, object]] = {}
    for route in ROUTES:
        before, palette = unpack_screen(original, route, "jp")
        after = replace_move_names(before, by_route[route], masks)
        slots = {int(row["slot"]) for row in by_route[route]}
        assert_unchanged_outside_slots(before, after, slots, route)
        characters, screen = encode_4bpp_screen(after)
        archive.replace_unpacked(f"cstat_jp_{route}.nbfc", characters)
        archive.replace_unpacked(f"cstat_jp_{route}.nbfs", screen)
        localized[route] = {
            "before": before,
            "after": after,
            "palette": palette,
            "character_tiles": len(characters) // 32,
        }

    rebuilt_data = archive.build()
    rebuilt = PackedArchive(rebuilt_data)
    for route in ROUTES:
        pixels, palette = unpack_screen(rebuilt, route, "jp")
        if pixels != localized[route]["after"] or palette != localized[route]["palette"]:
            raise ValueError(f"rebuilt character-status screen failed validation: {route}")
    expected_changes = {
        f"cstat_jp_{route}.{extension}"
        for route in ROUTES
        for extension in ("nbfc", "nbfs")
    }
    actual_changes = set(changed_entries(original, rebuilt))
    if actual_changes != expected_changes:
        raise ValueError(
            f"unexpected character-status archive changes: {actual_changes ^ expected_changes}"
        )

    result = finish_stage(
        stage,
        {RESOURCE_PATH: rebuilt_data},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_CharacterStatusTest",
        metadata=b"DBZ BR CN character status",
        resource_names={RESOURCE_PATH: "cstatus_bg_CN.bin"},
    )
    output_bytes = result.output_bytes

    source_archive = PackedArchive(source_rom.get_file(RESOURCE_PATH))
    sheet = Image.new("RGBA", (768, len(ROUTES) * 276), PREVIEW_BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    preview_paths = {}
    for row_index, route in enumerate(ROUTES):
        jp_pixels, jp_palette = unpack_screen(source_archive, route, "jp")
        en_pixels, en_palette = unpack_screen(source_archive, route, "en")
        images = {
            "JP": indexed_image(jp_pixels, jp_palette),
            "US": indexed_image(en_pixels, en_palette),
            "CN": indexed_image(localized[route]["after"], localized[route]["palette"]),
        }
        entry_sheet = Image.new("RGBA", (768, 276), PREVIEW_BACKGROUND)
        entry_draw = ImageDraw.Draw(entry_sheet)
        for column, label in enumerate(("JP", "US", "CN")):
            x = column * 256
            y = row_index * 276
            caption = f"{route} / {label}"
            entry_draw.text((x + 4, 2), caption, fill="white")
            entry_sheet.alpha_composite(images[label], (x, 20))
            draw.text((x + 4, y + 2), caption, fill="white")
            sheet.alpha_composite(images[label], (x, y + 20))
        entry_path = args.output_dir / f"{route}_JP_US_CN.png"
        entry_sheet.save(entry_path)
        preview_paths[route] = str(entry_path)
    preview_path = args.output_dir / "all_JP_US_CN.png"
    sheet.save(preview_path)

    report = {
        "localized_routes": list(ROUTES),
        "localized_move_names": len(rows),
        "preserved_content": (
            "stylized character names, Map Clear art, chart, progress rows, and locked slots"
        ),
        "style_policy": "localized functional move names; preserved stylized English art",
        "punctuation_style": "rendered Chinese fullwidth exclamation marks with the narrow UI glyph",
        "layout": {
            "slot_top": SLOT_TOP,
            "slot_height": SLOT_HEIGHT,
            "text_x": TEXT_X,
            "text_y_offset": TEXT_Y_OFFSET,
            "font_height": 12,
        },
        "font": str(args.bdf),
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "changed_from_base": result.changed_from_base,
        "changed_from_source": result.changed_from_source,
        "changed_archive_entries": sorted(actual_changes),
        "resource_rom_range": [result.replaced[0].start, result.replaced[0].end],
        "previews": preview_paths,
        "output_resource": str(result.resource_paths[0]),
        "output_rom": str(result.rom_path),
        "output_patch": str(result.patch_path),
        "preview": str(preview_path),
    }
    write_report(stage, report)


if __name__ == "__main__":
    main()
