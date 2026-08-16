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
from dbzbr.nitro_bg import decode_bgr555_palette
from dbzbr.uistage import (
    add_stage_arguments,
    finish_stage,
    load_stage,
    write_report,
)

MAP_TITLE_PATH = "romdata/scene/maptitle_jp_tex.bin"
MAP_TITLE_EN_PATH = "romdata/scene/maptitle_en_tex.bin"
CLEAR_X = 14
TEXT_X = 18
TEXT_Y = 1
ROW_HEIGHT = 16
TEXT_HEIGHT = 12
BACKGROUND_INDEX = 2
FOREGROUND_INDEX = 1
TITLE_PUNCTUATION = str.maketrans({"？": "?"})


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def display_text(text: str) -> str:
    return text.translate(TITLE_PUNCTUATION)


def decode_4bpp_linear(data: bytes, *, width: int = 256) -> list[list[int]]:
    if len(data) * 2 % width:
        raise ValueError("4bpp texture does not fit the selected width")
    values = [value for byte in data for value in (byte & 0x0F, byte >> 4)]
    height = len(values) // width
    return [values[y * width : (y + 1) * width] for y in range(height)]


def encode_4bpp_linear(pixels: list[list[int]]) -> bytes:
    if not pixels or any(len(row) != len(pixels[0]) for row in pixels):
        raise ValueError("indexed texture must be rectangular")
    values = [value for row in pixels for value in row]
    if len(values) % 2 or any(not 0 <= value < 16 for value in values):
        raise ValueError("4bpp pixels must contain an even number of 0..15 values")
    return bytes(values[index] | (values[index + 1] << 4) for index in range(0, len(values), 2))


def text_width(text: str, masks: dict[str, list[list[bool]]]) -> int:
    return sum(len(masks[character][0]) for character in text)


def draw_line(
    pixels: list[list[int]],
    text: str,
    masks: dict[str, list[list[bool]]],
    *,
    x: int,
    y: int,
) -> None:
    cursor_x = x
    for character in text:
        mask = masks[character]
        for glyph_y, row in enumerate(mask):
            for glyph_x, foreground in enumerate(row):
                if foreground:
                    pixels[y + glyph_y][cursor_x + glyph_x] = FOREGROUND_INDEX
        cursor_x += len(mask[0])


def replace_title(
    pixels: list[list[int]],
    row_index: int,
    text: str,
    masks: dict[str, list[list[bool]]],
) -> tuple[int, int, int, int]:
    if not 0 <= row_index < 4:
        raise ValueError(f"title row outside 0..3: {row_index}")
    width = text_width(text, masks)
    if width > 256 - TEXT_X:
        raise ValueError(f"map title does not fit ({width}px): {text}")
    base_y = row_index * ROW_HEIGHT
    rect = (CLEAR_X, base_y + 1, 256, base_y + 15)
    for y in range(rect[1], rect[3]):
        for x in range(rect[0], rect[2]):
            pixels[y][x] = BACKGROUND_INDEX
    draw_line(pixels, text, masks, x=TEXT_X, y=base_y + TEXT_Y)
    if any(
        pixels[y][x] != BACKGROUND_INDEX
        for y in range(rect[1], rect[3])
        for x in range(CLEAR_X, TEXT_X)
    ):
        raise ValueError(f"map-title icon gap was overwritten: row {row_index}")
    return rect


def assert_unchanged_outside_rects(
    before: list[list[int]],
    after: list[list[int]],
    rects: list[tuple[int, int, int, int]],
    label: str,
) -> None:
    for y, (before_row, after_row) in enumerate(zip(before, after)):
        for x, (old, new) in enumerate(zip(before_row, after_row)):
            if old == new:
                continue
            if not any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in rects):
                raise ValueError(f"pixel outside localized rows changed: {label} at {x},{y}")


def render(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (len(pixels[0]), len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            image.putpixel((x, y), palette[value])
    return image


def changed_entries(before: PackedArchive, after: PackedArchive) -> list[dict[str, object]]:
    if before.names() != after.names():
        raise ValueError("archive entry order changed")
    return [
        {"index": index, "name": old.name}
        for index, (old, new) in enumerate(zip(before.entries, after.entries))
        if before.decompress(old.packed_data) != after.decompress(new.packed_data)
    ]


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized story-map and tutorial titles."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_save_test/DBZ_Bukuu_Ressen_CN_UI_SaveTest.nds",
        table="data/translation/ui_map_titles.tsv",
        output_dir="build/ui_map_title_test",
    )
    args = parser.parse_args()

    rows = read_rows(args.table)
    keys = [(row["route"], row["frame"], int(row["row"])) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate route/frame/row keys in map-title table")
    characters = "".join(display_text(row["simplified_chinese"]) for row in rows)
    stage = load_stage(args, PROJECT_ROOT, characters=characters)
    masks = stage.masks
    source_rom = stage.source_rom
    original_data = stage.base_rom.get_file(MAP_TITLE_PATH)
    original_archive = PackedArchive(original_data)
    archive = PackedArchive(original_data)

    rows_by_texture: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_texture[(row["route"], row["frame"])].append(row)

    localized_pixels: dict[tuple[str, str], list[list[int]]] = {}
    for (route, frame), texture_rows in sorted(rows_by_texture.items()):
        texture_name = f"titlebar_{route}_{frame}.ntft"
        before = decode_4bpp_linear(archive.unpack(texture_name))
        pixels = [line[:] for line in before]
        rects = []
        for row in sorted(texture_rows, key=lambda item: int(item["row"])):
            rects.append(
                replace_title(
                    pixels,
                    int(row["row"]),
                    display_text(row["simplified_chinese"]),
                    masks,
                )
            )
        assert_unchanged_outside_rects(before, pixels, rects, texture_name)
        archive.replace_unpacked(texture_name, encode_4bpp_linear(pixels))
        localized_pixels[(route, frame)] = pixels

    rebuilt_data = archive.build()
    result = finish_stage(
        stage,
        {MAP_TITLE_PATH: rebuilt_data},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_MapTitleTest",
        metadata=b"DBZ BR CN story map titles",
        resource_names={MAP_TITLE_PATH: "maptitle_jp_cn_tex.bin"},
    )
    output_bytes = result.output_bytes

    rebuilt_archive = PackedArchive(rebuilt_data)
    changes = changed_entries(original_archive, rebuilt_archive)
    expected_names = {
        f"titlebar_{route}_{frame}.ntft" for route, frame in rows_by_texture
    }
    if {item["name"] for item in changes} != expected_names:
        raise ValueError(f"unexpected map-title archive changes: {changes}")
    for key, expected_pixels in localized_pixels.items():
        route, frame = key
        actual = decode_4bpp_linear(rebuilt_archive.unpack(f"titlebar_{route}_{frame}.ntft"))
        if actual != expected_pixels:
            raise ValueError(f"rebuilt map title failed validation: {route}/{frame}")


    source_jp = PackedArchive(source_rom.get_file(MAP_TITLE_PATH))
    source_en = PackedArchive(source_rom.get_file(MAP_TITLE_EN_PATH))
    preview_paths = []
    for route in sorted({row["route"] for row in rows}):
        sheet = Image.new("RGBA", (768, 5 * 84), (36, 39, 48, 255))
        draw = ImageDraw.Draw(sheet)
        for frame_index in range(5):
            frame = f"{frame_index:02d}"
            y = frame_index * 84
            palette_name = f"titlebar_{route}_00.ntfp"
            texture_name = f"titlebar_{route}_{frame}.ntft"
            sources = {
                "JP": source_jp,
                "EN": source_en,
                "CN": rebuilt_archive,
            }
            for column, (label, source) in enumerate(sources.items()):
                draw.text((column * 256 + 4, y + 2), f"{route}/{frame} / {label}", fill="white")
                sheet.alpha_composite(
                    render(
                        decode_4bpp_linear(source.unpack(texture_name)),
                        source.unpack(palette_name),
                    ),
                    (column * 256, y + 20),
                )
        preview_path = args.output_dir / f"{route}_JP_EN_CN.png"
        sheet.save(preview_path)
        preview_paths.append(str(preview_path))

    report = {
        "localized_routes": sorted({row["route"] for row in rows}),
        "localized_titles": len(rows),
        "localized_textures": len(rows_by_texture),
        "preserved_routes": [],
        "preserved_content": "blank slots and developer title-test placeholders",
        "style_policy": "localized all visible story, tutorial, and MAXIMUM challenge titles",
        "punctuation_style": "rendered fullwidth Chinese exclamation/question marks with the original narrow halfwidth title glyphs",
        "font": str(args.bdf),
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "changed_from_base": result.changed_from_base,
        "changed_from_source": result.changed_from_source,
        "changed_archive_entries": changes,
        "resource_rom_range": [result.replaced[0].start, result.replaced[0].end],
        "previews": preview_paths,
        "output_resource": str(result.resource_paths[0]),
        "output_rom": str(result.rom_path),
        "output_patch": str(result.patch_path),
    }
    write_report(stage, report, "build_report.json")


if __name__ == "__main__":
    main()
