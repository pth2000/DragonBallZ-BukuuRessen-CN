#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nitro_bg import decode_bgr555_palette
from dbzbr.uistage import (
    add_stage_arguments,
    finish_stage,
    load_stage,
)

RESOURCE_PATH = "romdata/data/DataModeDataImage.bin"
EN_RESOURCE_PATH = "romdata/data/DataModeDataImage_EN.bin"
BACKGROUND = (36, 39, 48, 255)


@dataclass(frozen=True)
class TextRegion:
    rect: tuple[int, int, int, int]
    text_x: int
    text_y: int
    background_index: int
    foreground_index: int
    clear_foreground_only: bool = False


REGIONS = {
    "arts_title": TextRegion((36, 10, 176, 25), 38, 11, 1, 15, True),
    "arts_detail": TextRegion((38, 26, 176, 39), 40, 26, 13, 1),
    "special_title": TextRegion((36, 10, 170, 25), 38, 11, 1, 15, True),
    "special_detail": TextRegion((37, 26, 204, 79), 38, 27, 13, 1),
    "special_title_secondary": TextRegion((36, 94, 170, 109), 38, 95, 1, 15, True),
    "special_detail_secondary": TextRegion((37, 110, 204, 163), 38, 111, 13, 1),
    "team_title": TextRegion((27, 11, 133, 26), 28, 12, 13, 1, True),
}
COMMAND_ICON_SCAN_RECT = (40, 27, 176, 38)
COMMAND_ICON_GAP = 2
COMMAND_ICON_WIDTH = 31
TEXT_LINE_HEIGHT = 15


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def texture_name(language: str, character: str, item: str) -> str:
    return f"{language}\\{character}\\data_{character}_{item}.ntft"


def palette_name(language: str, character: str, item: str) -> str:
    if item in {"ex2", "ex3"}:
        item = "ex1"
    elif item.startswith("sp"):
        item = "sp1"
    elif item.startswith("team"):
        item = "team1"
    # The archive stores one shared palette set under the first character
    # (gkn); every other character contains textures only.
    return f"{language}\\gkn\\data_gkn_{item}.ntfp"


def decode_4bpp_linear(data: bytes, *, width: int = 256) -> list[list[int]]:
    if len(data) * 2 % width:
        raise ValueError("4bpp texture does not fit the selected width")
    values = [value for packed in data for value in (packed & 0x0F, packed >> 4)]
    return [values[y * width : (y + 1) * width] for y in range(len(values) // width)]


def encode_4bpp_linear(pixels: list[list[int]]) -> bytes:
    if not pixels or any(len(row) != len(pixels[0]) for row in pixels):
        raise ValueError("indexed texture must be rectangular")
    values = [value for row in pixels for value in row]
    if len(values) % 2 or any(not 0 <= value < 16 for value in values):
        raise ValueError("4bpp pixels must contain an even number of 0..15 values")
    return bytes(
        values[index] | (values[index + 1] << 4)
        for index in range(0, len(values), 2)
    )


def text_width(text: str, masks: dict[str, list[list[bool]]]) -> int:
    return sum(len(masks[character][0]) for character in text)


def replace_text(
    pixels: list[list[int]],
    text: str,
    masks: dict[str, list[list[bool]]],
    region: TextRegion,
) -> None:
    x0, y0, x1, y1 = region.rect
    lines = text.split("\\n")
    widths = [text_width(line, masks) for line in lines]
    if any(width > x1 - region.text_x for width in widths):
        raise ValueError(
            f"text is too wide for its Data Mode region ({max(widths)}px): {text}"
        )
    for line_index, line in enumerate(lines):
        line_y = region.text_y + line_index * TEXT_LINE_HEIGHT
        if any(
            line_y < y0 or line_y + len(masks[character]) > y1
            for character in line
        ):
            raise ValueError(f"glyph is too tall for its Data Mode region: {text}")
    if region.clear_foreground_only:
        for line_index, line in enumerate(lines):
            cursor_x = region.text_x
            line_y = region.text_y + line_index * TEXT_LINE_HEIGHT
            for character in line:
                mask = masks[character]
                for glyph_y, mask_row in enumerate(mask):
                    for glyph_x, foreground in enumerate(mask_row):
                        if not foreground:
                            continue
                        existing = pixels[line_y + glyph_y][cursor_x + glyph_x]
                        if existing not in {
                            region.background_index,
                            region.foreground_index,
                        }:
                            raise ValueError(
                                f"text would overwrite card artwork: {text}"
                            )
                cursor_x += len(mask[0])
    for y in range(y0, y1):
        for x in range(x0, x1):
            if (
                not region.clear_foreground_only
                or pixels[y][x] == region.foreground_index
            ):
                pixels[y][x] = region.background_index
    for line_index, line in enumerate(lines):
        cursor_x = region.text_x
        line_y = region.text_y + line_index * TEXT_LINE_HEIGHT
        for character in line:
            mask = masks[character]
            for glyph_y, mask_row in enumerate(mask):
                for glyph_x, foreground in enumerate(mask_row):
                    if foreground:
                        pixels[line_y + glyph_y][cursor_x + glyph_x] = (
                            region.foreground_index
                        )
            cursor_x += len(mask[0])


def row_regions(row: dict[str, str]) -> list[tuple[str, str]]:
    category = row["category"]
    if category == "arts":
        return [
            ("arts_title", row["simplified_chinese"]),
            ("arts_detail", row["simplified_chinese_detail"]),
        ]
    if category == "special":
        regions = [
            ("special_title", row["simplified_chinese"]),
            ("special_detail", row["simplified_chinese_detail"]),
        ]
        if row.get("secondary_simplified_chinese"):
            regions.extend(
                [
                    ("special_title_secondary", row["secondary_simplified_chinese"]),
                    (
                        "special_detail_secondary",
                        row["secondary_simplified_chinese_detail"],
                    ),
                ]
            )
        return regions
    if category == "team":
        return [("team_title", row["simplified_chinese"])]
    raise ValueError(f"unknown Data Mode category: {category}")


def arts_detail_region(item: str) -> TextRegion:
    region = REGIONS["arts_detail"]
    if item != "ex4":
        return region
    return TextRegion(
        region.rect,
        region.text_x,
        region.text_y,
        11,
        region.foreground_index,
    )


def protect_solid_bottom_border(
    pixels: list[list[int]],
    region: TextRegion,
    *,
    protected_text_y_offset: int = 0,
) -> TextRegion:
    """Keep card variants whose bottom border lies inside the generic detail box."""
    x0, y0, x1, y1 = region.rect
    border_y = y1 - 1
    if y1 <= y0 or not all(
        pixels[border_y][x] == region.foreground_index for x in range(x0, x1)
    ):
        return region
    return TextRegion(
        (x0, y0 + min(0, protected_text_y_offset), x1, border_y),
        region.text_x,
        region.text_y + protected_text_y_offset,
        region.background_index,
        region.foreground_index,
        region.clear_foreground_only,
    )


def place_command_icons(
    before: list[list[int]],
    after: list[list[int]],
    text: str,
    masks: dict[str, list[list[bool]]],
    region: TextRegion,
) -> None:
    scan_x0, source_y0, scan_x1, source_y1 = COMMAND_ICON_SCAN_RECT
    icon_pixels = [
        (x, y)
        for y in range(source_y0, source_y1)
        for x in range(scan_x0, scan_x1)
        if before[y][x]
        not in {0, region.background_index, region.foreground_index}
    ]
    if not icon_pixels:
        raise ValueError("command icons could not be located")
    source_x1 = max(x for x, _ in icon_pixels) + 1
    source_x0 = source_x1 - COMMAND_ICON_WIDTH
    destination_x = region.text_x + text_width(text, masks) + COMMAND_ICON_GAP
    icon_width = source_x1 - source_x0
    if destination_x + icon_width > region.rect[2]:
        raise ValueError(f"command text and icons do not fit: {text}")
    for y in range(source_y0, source_y1):
        for offset_x, x in enumerate(range(source_x0, source_x1)):
            after[y][destination_x + offset_x] = before[y][x]


def assert_unchanged_outside_regions(
    before: list[list[int]],
    after: list[list[int]],
    regions: list[TextRegion],
    label: str,
) -> None:
    rects = [region.rect for region in regions]
    for y, (before_row, after_row) in enumerate(zip(before, after)):
        for x, (old, new) in enumerate(zip(before_row, after_row)):
            if old == new:
                continue
            if not any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in rects):
                raise ValueError(f"pixel outside localized regions changed: {label} at {x},{y}")


def assert_region_artwork_preserved(
    before: list[list[int]],
    after: list[list[int]],
    region: TextRegion,
    label: str,
) -> None:
    if not region.clear_foreground_only:
        return
    x0, y0, x1, y1 = region.rect
    text_indices = {region.background_index, region.foreground_index}
    for y in range(y0, y1):
        for x in range(x0, x1):
            if before[y][x] not in text_indices and before[y][x] != after[y][x]:
                raise ValueError(
                    f"card artwork inside text region changed: {label} at {x},{y}"
                )


def indexed_image(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (len(pixels[0]), len(pixels)), BACKGROUND)
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def changed_entries(before: PackedArchive, after: PackedArchive) -> list[str]:
    if before.names() != after.names():
        raise ValueError("Data Mode archive entry order changed")
    return [
        old.name
        for old, new in zip(before.entries, after.entries)
        if before.decompress(old.packed_data) != after.decompress(new.packed_data)
    ]


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized Data Mode character cards."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_character_status_test/DBZ_Bukuu_Ressen_CN_UI_CharacterStatusTest.nds",
        table="data/translation/ui_character_data.tsv",
        output_dir="build/ui_character_data_test",
    )
    parser.add_argument("--preview-scale", type=int, default=2)
    parser.add_argument(
        "--clear-detail",
        action="append",
        default=[],
        metavar="CHARACTER/ITEM",
        help="diagnostic: clear an ARTS detail row, including its command icons",
    )
    args = parser.parse_args()

    rows = read_rows(args.table)
    keys = [(row["character"], row["item"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate Data Mode character/item rows")
    if not rows or any(not row["simplified_chinese"] for row in rows):
        raise ValueError("missing Data Mode translation")
    clear_detail_keys: set[tuple[str, str]] = set()
    for value in args.clear_detail:
        parts = value.split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"invalid --clear-detail key: {value}")
        clear_detail_keys.add((parts[0], parts[1]))
    unknown_clear_keys = clear_detail_keys - set(keys)
    if unknown_clear_keys:
        raise ValueError(f"unknown --clear-detail keys: {sorted(unknown_clear_keys)}")
    for row in rows:
        if row["category"] == "special" and not row["simplified_chinese_detail"]:
            raise ValueError(f"missing Data Mode detail translation: {row['character']}/{row['item']}")
        if (
            row.get("secondary_simplified_chinese")
            and not row.get("secondary_simplified_chinese_detail")
        ):
            raise ValueError(
                f"missing secondary Data Mode detail translation: "
                f"{row['character']}/{row['item']}"
            )
        if (
            row["category"] == "arts"
            and row["requires_detail"] == "yes"
            and not row["simplified_chinese_detail"]
        ):
            raise ValueError(f"missing Data Mode detail translation: {row['character']}/{row['item']}")

    characters = "".join(
        character
        for row in rows
        for _, text in row_regions(row)
        for character in text
    )
    stage = load_stage(args, PROJECT_ROOT, characters=characters)
    masks = stage.masks
    source_rom = stage.source_rom
    original_data = stage.base_rom.get_file(RESOURCE_PATH)
    original_archive = PackedArchive(original_data)
    archive = PackedArchive(original_data)
    localized_pixels: dict[tuple[str, str], list[list[int]]] = {}

    for row in rows:
        character, item = row["character"], row["item"]
        name = texture_name("JA", character, item)
        before = decode_4bpp_linear(archive.unpack(name))
        after = [pixel_row[:] for pixel_row in before]
        used_regions = []
        for region_name, text in row_regions(row):
            clear_detail = (
                (character, item) in clear_detail_keys
                and region_name == "arts_detail"
            )
            if clear_detail:
                text = ""
            region = (
                arts_detail_region(item)
                if region_name == "arts_detail"
                else REGIONS[region_name]
            )
            if region_name.endswith("detail") or region_name.endswith("detail_secondary"):
                region = protect_solid_bottom_border(
                    before,
                    region,
                    protected_text_y_offset=-1 if region_name == "arts_detail" else 0,
                )
            replace_text(after, text, masks, region)
            assert_region_artwork_preserved(
                before, after, region, f"{character}/{item}/{region_name}"
            )
            used_regions.append(region)
            if region_name == "arts_detail" and not clear_detail:
                place_command_icons(before, after, text, masks, region)
        assert_unchanged_outside_regions(before, after, used_regions, f"{character}/{item}")
        archive.replace_unpacked(name, encode_4bpp_linear(after))
        localized_pixels[(character, item)] = after

    rebuilt_data = archive.build()
    result = finish_stage(
        stage,
        {RESOURCE_PATH: rebuilt_data},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_CharacterDataTest",
        metadata=b"DBZ BR CN Data Mode character cards",
        resource_names={RESOURCE_PATH: "DataModeDataImage_CN.bin"},
    )
    output_bytes = result.output_bytes
    rom_path = result.rom_path
    patch_path = result.patch_path

    rebuilt_archive = PackedArchive(rebuilt_data)
    expected_changes = {texture_name("JA", character, item) for character, item in keys}
    actual_changes = set(changed_entries(original_archive, rebuilt_archive))
    if actual_changes != expected_changes:
        raise ValueError(f"unexpected changed Data Mode entries: {sorted(actual_changes ^ expected_changes)}")
    for key, expected in localized_pixels.items():
        actual = decode_4bpp_linear(rebuilt_archive.unpack(texture_name("JA", *key)))
        if actual != expected:
            raise ValueError(f"rebuilt Data Mode texture failed validation: {key}")

    jp_source = PackedArchive(source_rom.get_file(RESOURCE_PATH))
    en_source = PackedArchive(source_rom.get_file(EN_RESOURCE_PATH))
    preview_paths = []
    preview_sheets: dict[str, list[Image.Image]] = {}
    for row in rows:
        character, item = row["character"], row["item"]
        images = []
        for language, source, pixels in (
            ("JP", jp_source, decode_4bpp_linear(jp_source.unpack(texture_name("JA", character, item)))),
            ("EN", en_source, decode_4bpp_linear(en_source.unpack(texture_name("EN", character, item)))),
            ("CN", rebuilt_archive, localized_pixels[(character, item)]),
        ):
            archive_language = "EN" if language == "EN" else "JA"
            images.append(
                (
                    language,
                    indexed_image(
                        pixels,
                        source.unpack(palette_name(archive_language, character, item)),
                    ),
                )
            )
        height = max(image.height for _, image in images)
        sheet = Image.new("RGBA", (256 * 3, height + 18), BACKGROUND)
        draw = ImageDraw.Draw(sheet)
        for column, (language, image) in enumerate(images):
            draw.text((column * 256 + 4, 2), language, fill="white")
            sheet.alpha_composite(image, (column * 256, 18))
        if args.preview_scale != 1:
            sheet = sheet.resize(
                (sheet.width * args.preview_scale, sheet.height * args.preview_scale),
                Image.Resampling.NEAREST,
            )
        preview_path = args.output_dir / f"{character}_{item}_JP_EN_CN.png"
        sheet.save(preview_path)
        preview_paths.append(str(preview_path))
        preview_sheets.setdefault(character, []).append(sheet)

    combined_preview_paths = []
    preview_gap = 8 * args.preview_scale
    for character, sheets in preview_sheets.items():
        combined = Image.new(
            "RGBA",
            (
                max(sheet.width for sheet in sheets),
                sum(sheet.height for sheet in sheets)
                + preview_gap * (len(sheets) - 1),
            ),
            BACKGROUND,
        )
        y = 0
        for sheet in sheets:
            combined.alpha_composite(sheet, (0, y))
            y += sheet.height + preview_gap
        combined_path = args.output_dir / f"{character}_all_JP_EN_CN.png"
        combined.save(combined_path)
        combined_preview_paths.append(str(combined_path))

    report = {
        "localized_characters": sorted({row["character"] for row in rows}),
        "localized_cards": len(rows),
        "diagnostic_cleared_details": [
            f"{character}/{item}" for character, item in sorted(clear_detail_keys)
        ],
        "localized_entries": sorted(actual_changes),
        "preserved_content": [
            "stylized ARTS / ULTIMATE ATTACKS / SPECIAL / TEAM ARTS headings",
            "Romanized character-name art",
            "character portrait and command-button graphics",
            "all Data Mode portraits and non-text card artwork",
        ],
        "punctuation_style": "rendered Chinese fullwidth exclamation marks with the narrow UI glyph",
        "border_handling": "preserved solid bottom borders that fall inside generic detail regions",
        "border_adjacent_text": "raised single-line command text by 1px to match the Japanese baseline",
        "font": str(args.bdf),
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "changed_rom_files_from_base": result.changed_from_base,
        "changed_rom_files_from_source": result.changed_from_source,
        "previews": preview_paths,
        "combined_previews": combined_preview_paths,
    }
    report_path = args.output_dir / "audit.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(rom_path)
    print(patch_path)
    print(report_path)
    print(f"localized cards: {len(rows)}")
    print(f"output SHA256: {report['output_rom_sha256']}")
    print(f"patch SHA256: {report['patch_sha256']}")


if __name__ == "__main__":
    main()
