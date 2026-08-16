#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import struct
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nitro_bg import decode_4bpp_screen, decode_bgr555_palette
from dbzbr.uistage import (
    add_stage_arguments,
    finish_stage,
    load_stage,
    write_report,
)

VS_PATH = "romdata/game/vsmode.bin"
SCREEN_LAYOUT = {
    ("msg_j", "host"): {"rect": (40, 264, 216, 326), "background": 0, "color": 2},
    ("msg_j", "join"): {"rect": (40, 344, 216, 406), "background": 0, "color": 2},
    ("msg_j", "challenge"): {
        "rect": (40, 445, 216, 466), "background": 0, "color": 2
    },
    ("obi_j", "overflow"): {
        "rect": (8, 168, 248, 185), "background": 7, "color": 1
    },
    ("vsmsg_j", "standby"): {
        "rect": (48, 189, 208, 210), "background": 0, "color": 1
    },
    ("vsmsg_j", "failed"): {
        "rect": (48, 221, 208, 239), "background": 0, "color": 1
    },
    ("vsmsg_j", "press_a"): {
        "rect": (48, 239, 208, 256), "background": 0, "color": 13
    },
}
SCREEN_INFO = {
    "obi_j": {"palette": "obi_e.nbfp", "palette_bank": 9, "us_stem": "obi_e"},
    "msg_j": {"palette": "msg_j.nbfp", "palette_bank": 1, "us_stem": "msg_e"},
    "vsmsg_j": {"palette": "connect.nbfp", "palette_bank": 0, "us_stem": "vsmsg_e"},
}
LINE_HEIGHT = 15


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def decode_local_screen(archive: PackedArchive, stem: str) -> list[list[int]]:
    return [
        [value & 0xF for value in row]
        for row in decode_4bpp_screen(
            archive.unpack(f"{stem}.nbfc"), archive.unpack(f"{stem}.nbfs")
        )
    ]


def encode_tile(tile: tuple[int, ...]) -> bytes:
    if len(tile) != 64 or any(not 0 <= value < 16 for value in tile):
        raise ValueError("a 4bpp tile must contain 64 palette indices")
    output = bytearray(32)
    for y in range(8):
        for x in range(0, 8, 2):
            output[y * 4 + x // 2] = tile[y * 8 + x] | (tile[y * 8 + x + 1] << 4)
    return bytes(output)


def encode_screen(pixels: list[list[int]], palette_bank: int) -> tuple[bytes, bytes]:
    if (
        not pixels
        or len(pixels) % 8
        or any(len(row) != 256 for row in pixels)
        or any(not 0 <= value < 16 for row in pixels for value in row)
    ):
        raise ValueError("screen must be 256px wide, tile-aligned, and use 4bpp indices")
    if not 0 <= palette_bank < 16:
        raise ValueError("palette bank must be in range 0..15")
    blank = (0,) * 64
    tiles: list[tuple[int, ...]] = [blank]
    tile_indexes = {blank: 0}
    map_values = []
    for tile_y in range(len(pixels) // 8):
        for tile_x in range(32):
            tile = tuple(
                pixels[tile_y * 8 + y][tile_x * 8 + x]
                for y in range(8)
                for x in range(8)
            )
            tile_index = tile_indexes.get(tile)
            if tile_index is None:
                tile_index = len(tiles)
                if tile_index >= 1024:
                    raise ValueError("screen needs more than 1024 unique tiles")
                tiles.append(tile)
                tile_indexes[tile] = tile_index
            map_values.append(tile_index | (palette_bank << 12))
    return (
        b"".join(encode_tile(tile) for tile in tiles),
        struct.pack(f"<{len(map_values)}H", *map_values),
    )


def text_width(text: str, masks: dict[str, list[list[bool]]]) -> int:
    return sum(len(masks[character][0]) for character in text)


def clear_rect(
    pixels: list[list[int]], rect: tuple[int, int, int, int], value: int
) -> None:
    x0, y0, x1, y1 = rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            pixels[y][x] = value


def draw_line(
    pixels: list[list[int]],
    line: str,
    masks: dict[str, list[list[bool]]],
    x: int,
    y: int,
    value: int,
) -> None:
    cursor_x = x
    for character in line:
        mask = masks[character]
        for glyph_y, row in enumerate(mask):
            for glyph_x, foreground in enumerate(row):
                if foreground:
                    pixels[y + glyph_y][cursor_x + glyph_x] = value
        cursor_x += len(mask[0])


def replace_text(
    pixels: list[list[int]],
    text: str,
    masks: dict[str, list[list[bool]]],
    layout: dict[str, object],
) -> None:
    rect = layout["rect"]
    assert isinstance(rect, tuple)
    background = int(layout["background"])
    color = int(layout["color"])
    clear_rect(pixels, rect, background)
    lines = text.split("\\n")
    widths = [text_width(line, masks) for line in lines]
    block_width = max(widths, default=0)
    glyph_height = max(
        (len(masks[character]) for line in lines for character in line), default=0
    )
    block_height = glyph_height + max(0, len(lines) - 1) * LINE_HEIGHT
    x0, y0, x1, y1 = rect
    if block_width > x1 - x0 or block_height > y1 - y0:
        raise ValueError(f"text does not fit {rect}: {text}")
    block_x = x0 + (x1 - x0 - block_width) // 2
    start_y = y0 + (y1 - y0 - block_height) // 2
    for line_index, line in enumerate(lines):
        draw_line(
            pixels,
            line,
            masks,
            block_x,
            start_y + line_index * LINE_HEIGHT,
            color,
        )


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
                raise ValueError(f"pixel outside localized regions changed: {label} at {x},{y}")


def render(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (len(pixels[0]), len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def preview_layout(pixels: list[list[int]]) -> list[list[int]]:
    """Arrange two sequential 32x32 screen blocks as the game's 512x256 BG."""
    if len(pixels) == 512 and all(len(row) == 256 for row in pixels):
        return [pixels[y] + pixels[y + 256] for y in range(256)]
    return pixels


def changed_entries(before: PackedArchive, after: PackedArchive) -> list[str]:
    if before.names() != after.names():
        raise ValueError("archive entry order changed")
    return [
        old.name
        for old, new in zip(before.entries, after.entries)
        if before.decompress(old.packed_data) != after.decompress(new.packed_data)
    ]


def main() -> None:
    parser = add_stage_arguments(
        argparse.ArgumentParser(description="Build localized wireless VS interface."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_map_title_test/DBZ_Bukuu_Ressen_CN_UI_MapTitleTest.nds",
        table="data/translation/ui_vs_messages.tsv",
        output_dir="build/ui_vs_test",
    )
    args = parser.parse_args()

    rows = read_rows(args.table)
    keys = {(row["screen"], row["id"]) for row in rows}
    if keys != set(SCREEN_LAYOUT) or len(keys) != len(rows):
        raise ValueError("wireless translation rows differ from expected layouts")
    characters = "".join(row["simplified_chinese"].replace("\\n", "") for row in rows)
    stage = load_stage(args, PROJECT_ROOT, characters=characters)
    masks = stage.masks
    source_rom = stage.source_rom
    original_data = stage.base_rom.get_file(VS_PATH)
    original = PackedArchive(original_data)
    archive = PackedArchive(original_data)

    before_pixels = {stem: decode_local_screen(original, stem) for stem in SCREEN_INFO}
    after_pixels = {stem: [row[:] for row in pixels] for stem, pixels in before_pixels.items()}
    for row in rows:
        replace_text(
            after_pixels[row["screen"]],
            row["simplified_chinese"],
            masks,
            SCREEN_LAYOUT[(row["screen"], row["id"])],
        )
    for stem, info in SCREEN_INFO.items():
        rects = [
            layout["rect"]
            for (screen, _), layout in SCREEN_LAYOUT.items()
            if screen == stem
        ]
        assert all(isinstance(rect, tuple) for rect in rects)
        assert_unchanged_outside_rects(before_pixels[stem], after_pixels[stem], rects, stem)
        characters_data, screen_data = encode_screen(
            after_pixels[stem], int(info["palette_bank"])
        )
        archive.replace_unpacked(f"{stem}.nbfc", characters_data)
        archive.replace_unpacked(f"{stem}.nbfs", screen_data)

    rebuilt_data = archive.build()
    rebuilt = PackedArchive(rebuilt_data)
    for stem in SCREEN_INFO:
        if decode_local_screen(rebuilt, stem) != after_pixels[stem]:
            raise ValueError(f"rebuilt wireless screen failed validation: {stem}")
    expected_changes = {
        f"{stem}.{extension}"
        for stem in SCREEN_INFO
        for extension in ("nbfc", "nbfs")
    }
    actual_changes = set(changed_entries(original, rebuilt))
    if actual_changes != expected_changes:
        raise ValueError(
            f"unexpected wireless archive changes: {sorted(actual_changes ^ expected_changes)}"
        )

    result = finish_stage(
        stage,
        {VS_PATH: rebuilt_data},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_VSTest",
        metadata=b"DBZ BR CN wireless VS interface",
        resource_names={VS_PATH: "vsmode_CN.bin"},
    )
    output_bytes = result.output_bytes

    preview_paths = []
    source_archive = PackedArchive(source_rom.get_file(VS_PATH))
    for stem, info in SCREEN_INFO.items():
        palette = source_archive.unpack(str(info["palette"]))
        sources = {
            "JP": preview_layout(decode_local_screen(source_archive, stem)),
            "US": preview_layout(
                decode_local_screen(source_archive, str(info["us_stem"]))
            ),
            "CN": preview_layout(after_pixels[stem]),
        }
        width = len(next(iter(sources.values()))[0])
        height = len(next(iter(sources.values())))
        sheet = Image.new("RGBA", (width * 3, height + 20), (36, 39, 48, 255))
        draw = ImageDraw.Draw(sheet)
        for column, (label, pixels) in enumerate(sources.items()):
            draw.text((column * width + 4, 2), f"{stem} / {label}", fill="white")
            sheet.alpha_composite(render(pixels, palette), (column * width, 20))
        preview_path = args.output_dir / f"{stem}_JP_US_CN.png"
        sheet.save(preview_path)
        preview_paths.append(str(preview_path))

    report = {
        "localized_messages": len(rows),
        "localized_screens": sorted(SCREEN_INFO),
        "preserved_content": "VS BATTLE title, connection window, icons, palettes, and non-Japanese language groups",
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
    }
    write_report(stage, report)


if __name__ == "__main__":
    main()
