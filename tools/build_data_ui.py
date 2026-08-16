#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw, ImageFont

from dbzbr.archive import PackedArchive
from dbzbr.font import (
    centered_text_block_origin,
    load_ui_bdf_masks,
    ui_glyph_character,
)
from dbzbr.nitro_bg import decode_4bpp_screen, decode_bgr555_palette, encode_4bpp_screen
from dbzbr.uistage import (
    add_stage_arguments,
    finish_stage,
    load_stage,
    write_report,
)

HELP_PATH = "romdata/data/HelpJA.bin"
HELP_US_PATH = "romdata/data/HelpUS.bin"
DATA_PATH = "romdata/data/DataSubScrJA.bin"
DATA_US_PATH = "romdata/data/DataSubScrUS.bin"
A3I5_BACKGROUND = 0xA0
HELP_LINE_HEIGHT = 15
HELP_LAYOUT = {
    ("arts_help_JA", "rapid"): {
        "rect": (20, 4, 256, 65), "heading": (23, 5), "body": (23, 22)
    },
    ("arts_help_JA", "charge"): {
        "rect": (20, 65, 256, 128), "heading": (23, 69), "body": (23, 86)
    },
    ("arts_help_JA", "ultimate"): {
        "rect": (20, 128, 256, 200), "heading": (23, 133), "body": (23, 150)
    },
    ("sp_help_JA", "body"): {"rect": (20, 40, 240, 154)},
    ("sup_help_JA", "body"): {"rect": (20, 28, 240, 145)},
    ("teamarts_help_JA", "body"): {"rect": (16, 32, 240, 154)},
}
DATA_LAYOUT = {
    ("df00", "prompt"): (0, 0, 256, 15),
    ("df00", "arts"): (80, 33, 176, 55),
    ("df00", "special"): (80, 72, 176, 95),
    ("df00", "team"): (64, 111, 192, 135),
    ("df01", "prompt"): (0, 0, 256, 15),
    ("df01", "support"): (80, 39, 176, 64),
    ("df01", "team"): (64, 97, 192, 121),
    ("df02", "team"): (64, 111, 192, 135),
    ("df03", "team"): (64, 97, 192, 121),
}
DATA_TEXT_INDEX = 15
DATA_LABEL_SIZE = 16


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def text_width(text: str, masks: dict[str, list[list[bool]]]) -> int:
    return sum(len(masks[character][0]) for character in text)


def load_label_masks(
    path: Path, characters: str
) -> dict[str, list[list[bool]]]:
    if path.suffix.lower() == ".bdf":
        return load_ui_bdf_masks(path, characters)
    if path.suffix.lower() not in {".ttf", ".otf"}:
        raise ValueError(f"unsupported Data label font format: {path}")
    font = ImageFont.truetype(str(path), DATA_LABEL_SIZE)
    result: dict[str, list[list[bool]]] = {}
    for character in set(characters):
        display_character = ui_glyph_character(character)
        glyph = Image.new("1", (DATA_LABEL_SIZE, DATA_LABEL_SIZE), 0)
        ImageDraw.Draw(glyph).text(
            (0, 0), display_character, font=font, fill=1, anchor="lt"
        )
        result[character] = [
            [bool(glyph.getpixel((x, y))) for x in range(DATA_LABEL_SIZE)]
            for y in range(DATA_LABEL_SIZE)
        ]
    return result


def clear_rect(
    pixels: list[list[int]], rect: tuple[int, int, int, int], value: int
) -> None:
    x0, y0, x1, y1 = rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            pixels[y][x] = value


def assert_unchanged_outside_rects(
    before: list[list[int]],
    after: list[list[int]],
    rects: list[tuple[int, int, int, int]],
    label: str,
) -> None:
    if len(before) != len(after) or any(len(left) != len(right) for left, right in zip(before, after)):
        raise ValueError(f"pixel dimensions changed: {label}")
    for y, (before_row, after_row) in enumerate(zip(before, after)):
        for x, (old, new) in enumerate(zip(before_row, after_row)):
            if old == new:
                continue
            if not any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in rects):
                raise ValueError(f"pixel outside localized regions changed: {label} at {x},{y}")


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


def decode_a3i5(texture: bytes) -> list[list[int]]:
    if len(texture) != 256 * 256:
        raise ValueError(f"expected a 256x256 A3I5 texture, got {len(texture)} bytes")
    return [list(texture[y * 256 : (y + 1) * 256]) for y in range(256)]


def encode_a3i5(pixels: list[list[int]]) -> bytes:
    if len(pixels) != 256 or any(len(row) != 256 for row in pixels):
        raise ValueError("A3I5 texture must be 256x256")
    return bytes(value for row in pixels for value in row)


def white_a3i5_value(palette_data: bytes) -> int:
    palette = decode_bgr555_palette(palette_data)
    white_index = max(range(len(palette)), key=lambda index: sum(palette[index][:3]))
    return 0xE0 | white_index


def replace_help_section(
    pixels: list[list[int]],
    row: dict[str, str],
    masks: dict[str, list[list[bool]]],
    foreground: int,
) -> None:
    key = (row["texture"], row["section"])
    layout = HELP_LAYOUT[key]
    rect = layout["rect"]
    assert isinstance(rect, tuple)
    clear_rect(pixels, rect, A3I5_BACKGROUND)
    heading = row["heading_chinese"]
    body_lines = row["body_chinese"].split("\\n")
    if heading:
        heading_pos = layout["heading"]
        body_pos = layout["body"]
        assert isinstance(heading_pos, tuple) and isinstance(body_pos, tuple)
        draw_line(pixels, heading, masks, heading_pos[0], heading_pos[1], foreground)
        for line_index, line in enumerate(body_lines):
            draw_line(
                pixels,
                line,
                masks,
                body_pos[0],
                body_pos[1] + line_index * HELP_LINE_HEIGHT,
                foreground,
            )
        return

    widths = [text_width(line, masks) for line in body_lines]
    block_width = max(widths, default=0)
    glyph_height = max(
        (len(masks[character]) for line in body_lines for character in line), default=0
    )
    block_height = glyph_height + max(0, len(body_lines) - 1) * HELP_LINE_HEIGHT
    x0, y0, x1, y1 = rect
    if block_width > x1 - x0 or block_height > y1 - y0:
        raise ValueError(f"help text does not fit: {key}")
    block_x, start_y = centered_text_block_origin(
        rect, body_lines, masks, HELP_LINE_HEIGHT
    )
    for line_index, line in enumerate(body_lines):
        draw_line(
            pixels,
            line,
            masks,
            block_x,
            start_y + line_index * HELP_LINE_HEIGHT,
            foreground,
        )


def replace_data_label(
    pixels: list[list[int]],
    text: str,
    rect: tuple[int, int, int, int],
    masks: dict[str, list[list[bool]]],
    *,
    left_align: bool = False,
) -> None:
    x0, y0, x1, y1 = rect
    protected = {
        (x, y): pixels[y][x]
        for y in range(y0, y1)
        for x in range(x0, x1)
        if pixels[y][x] < 12 and pixels[y][x] != 1
    }
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pixels[y][x] >= 12:
                pixels[y][x] = 1
    width = text_width(text, masks)
    height = max((len(masks[character]) for character in text), default=0)
    if width > x1 - x0 or height > y1 - y0:
        raise ValueError(f"data label does not fit: {text}")
    draw_line(
        pixels,
        text,
        masks,
        x0 if left_align else x0 + (x1 - x0 - width) // 2,
        y0 + (y1 - y0 - height) // 2,
        DATA_TEXT_INDEX,
    )
    changed_frame_pixels = [
        (x, y, value, pixels[y][x])
        for (x, y), value in protected.items()
        if pixels[y][x] != value
    ]
    if changed_frame_pixels:
        raise ValueError(
            f"data label overlaps protected frame pixels: {text} {changed_frame_pixels[:4]}"
        )


def render_a3i5(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (256, 256), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            alpha = (value >> 5) * 255 // 7
            if alpha:
                red, green, blue, _ = palette[value & 31]
                image.putpixel((x, y), (red, green, blue, alpha))
    return image


def render_nb(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (256, len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
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
        argparse.ArgumentParser(description="Build localized Data mode menus and help pages."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_practice_test/DBZ_Bukuu_Ressen_CN_UI_PracticeTest.nds",
        table=None,
        output_dir="build/ui_data_test",
        bdf=False,
    )
    parser.add_argument(
        "--help-table",
        type=Path,
        default=PROJECT_ROOT / "data/translation/ui_data_help.tsv",
    )
    parser.add_argument(
        "--menu-table",
        type=Path,
        default=PROJECT_ROOT / "data/translation/ui_data_menu.tsv",
    )
    parser.add_argument(
        "--help-bdf",
        type=Path,
        default=PROJECT_ROOT
        / "work/vendor/fusion-pixel-font/12px-monospaced-bdf-v2026.07.20/fusion-pixel-12px-monospaced-zh_hans.bdf",
    )
    parser.add_argument(
        "--menu-bdf",
        type=Path,
        default=PROJECT_ROOT
        / "work/vendor/fusion-pixel-font/12px-monospaced-bdf-v2026.07.20/fusion-pixel-12px-monospaced-zh_hans.bdf",
    )
    parser.add_argument(
        "--menu-label-font",
        "--menu-label-bdf",
        dest="menu_label_font",
        type=Path,
        default=PROJECT_ROOT
        / "work/vendor/zhengge-dianhei-16/ZhengGeDianHei-16.ttf",
        help="Native 16px pixel font used for Data mode category labels.",
    )
    args = parser.parse_args()

    help_rows = read_rows(args.help_table)
    menu_rows = read_rows(args.menu_table)
    if {(row["texture"], row["section"]) for row in help_rows} != set(HELP_LAYOUT):
        raise ValueError("help translation table entries differ from layouts")
    if {(row["screen"], row["id"]) for row in menu_rows} != set(DATA_LAYOUT):
        raise ValueError("data menu translation table entries differ from layouts")
    help_characters = "".join(
        row[field].replace("\\n", "")
        for row in help_rows
        for field in ("heading_chinese", "body_chinese")
    )
    prompt_characters = "".join(
        row["simplified_chinese"] for row in menu_rows if row["id"] == "prompt"
    )
    label_characters = "".join(
        row["simplified_chinese"] for row in menu_rows if row["id"] != "prompt"
    )
    help_masks = load_ui_bdf_masks(args.help_bdf, help_characters)
    menu_masks = load_ui_bdf_masks(args.menu_bdf, prompt_characters)
    menu_label_masks = load_label_masks(args.menu_label_font, label_characters)
    missing_help = sorted(set(help_characters) - set(help_masks))
    missing_prompt = sorted(set(prompt_characters) - set(menu_masks))
    missing_label = sorted(set(label_characters) - set(menu_label_masks))
    if missing_help or missing_prompt or missing_label:
        raise ValueError(
            "missing BDF glyphs: "
            f"help={missing_help}, prompt={missing_prompt}, label={missing_label}"
        )

    stage = load_stage(args, PROJECT_ROOT)
    source_rom = stage.source_rom
    original_help_data = stage.base_rom.get_file(HELP_PATH)
    original_menu_data = stage.base_rom.get_file(DATA_PATH)
    original_help = PackedArchive(original_help_data)
    original_menu = PackedArchive(original_menu_data)
    help_archive = PackedArchive(original_help_data)
    menu_archive = PackedArchive(original_menu_data)

    localized_help: dict[str, dict[str, object]] = {}
    rows_by_texture: dict[str, list[dict[str, str]]] = {}
    for row in help_rows:
        rows_by_texture.setdefault(row["texture"], []).append(row)
    for texture_name, rows in rows_by_texture.items():
        ntft_name = f"{texture_name}.ntft"
        ntfp_name = f"{texture_name}.ntfp"
        original_pixels = decode_a3i5(help_archive.unpack(ntft_name))
        pixels = [line[:] for line in original_pixels]
        palette_data = help_archive.unpack(ntfp_name)
        foreground = white_a3i5_value(palette_data)
        for row in rows:
            replace_help_section(pixels, row, help_masks, foreground)
        assert_unchanged_outside_rects(
            original_pixels,
            pixels,
            [HELP_LAYOUT[(row["texture"], row["section"])]["rect"] for row in rows],
            texture_name,
        )
        help_archive.replace_unpacked(ntft_name, encode_a3i5(pixels))
        localized_help[texture_name] = {
            "pixels": pixels,
            "palette": palette_data,
            "sections": [row["section"] for row in rows],
        }

    localized_menu: dict[str, dict[str, object]] = {}
    rows_by_screen: dict[str, list[dict[str, str]]] = {}
    for row in menu_rows:
        rows_by_screen.setdefault(row["screen"], []).append(row)
    for screen_name, rows in rows_by_screen.items():
        nbfc_name = f"{screen_name}.nbfc"
        nbfp_name = f"{screen_name}.nbfp"
        nbfs_name = f"{screen_name}.nbfs"
        original_pixels = decode_4bpp_screen(
            menu_archive.unpack(nbfc_name), menu_archive.unpack(nbfs_name)
        )
        pixels = [line[:] for line in original_pixels]
        for row in rows:
            is_prompt = row["id"] == "prompt"
            replace_data_label(
                pixels,
                row["simplified_chinese"],
                DATA_LAYOUT[(screen_name, row["id"])],
                menu_masks if is_prompt else menu_label_masks,
                left_align=is_prompt,
            )
        assert_unchanged_outside_rects(
            original_pixels,
            pixels,
            [DATA_LAYOUT[(screen_name, row["id"])] for row in rows],
            screen_name,
        )
        characters, screen = encode_4bpp_screen(pixels)
        menu_archive.replace_unpacked(nbfc_name, characters)
        menu_archive.replace_unpacked(nbfs_name, screen)
        localized_menu[screen_name] = {
            "pixels": pixels,
            "palette": menu_archive.unpack(nbfp_name),
            "character_tiles": len(characters) // 32,
        }

    rebuilt_help_data = help_archive.build()
    rebuilt_menu_data = menu_archive.build()
    result = finish_stage(
        stage,
        {HELP_PATH: rebuilt_help_data, DATA_PATH: rebuilt_menu_data},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_DataTest",
        metadata=b"DBZ BR CN Data mode UI",
        resource_names={HELP_PATH: "HelpJA_CN.bin", DATA_PATH: "DataSubScrJA_CN.bin"},
    )
    output_bytes = result.output_bytes

    rebuilt_help = PackedArchive(rebuilt_help_data)
    rebuilt_menu = PackedArchive(rebuilt_menu_data)
    for texture_name, item in localized_help.items():
        if decode_a3i5(rebuilt_help.unpack(f"{texture_name}.ntft")) != item["pixels"]:
            raise ValueError(f"rebuilt help texture failed validation: {texture_name}")
        if rebuilt_help.unpack(f"{texture_name}.ntfp") != item["palette"]:
            raise ValueError(f"help palette changed: {texture_name}")
    for screen_name, item in localized_menu.items():
        decoded = decode_4bpp_screen(
            rebuilt_menu.unpack(f"{screen_name}.nbfc"), rebuilt_menu.unpack(f"{screen_name}.nbfs")
        )
        if decoded != item["pixels"]:
            raise ValueError(f"rebuilt Data screen failed validation: {screen_name}")
        if rebuilt_menu.unpack(f"{screen_name}.nbfp") != item["palette"]:
            raise ValueError(f"Data palette changed: {screen_name}")

    help_changes = changed_entries(original_help, rebuilt_help)
    menu_changes = changed_entries(original_menu, rebuilt_menu)
    expected_help_names = {f"{name}.ntft" for name in rows_by_texture}
    expected_menu_names = {
        f"{name}.{extension}" for name in rows_by_screen for extension in ("nbfc", "nbfs")
    }
    if {item["name"] for item in help_changes} != expected_help_names:
        raise ValueError(f"unexpected Help archive changes: {help_changes}")
    if {item["name"] for item in menu_changes} != expected_menu_names:
        raise ValueError(f"unexpected Data archive changes: {menu_changes}")

    source_help_jp = PackedArchive(source_rom.get_file(HELP_PATH))
    source_help_us = PackedArchive(source_rom.get_file(HELP_US_PATH))
    help_previews: dict[str, str] = {}
    for texture_name, item in localized_help.items():
        us_name = texture_name.replace("_JA", "_US")
        previews = {
            "JP": render_a3i5(
                decode_a3i5(source_help_jp.unpack(f"{texture_name}.ntft")),
                source_help_jp.unpack(f"{texture_name}.ntfp"),
            ),
            "US": render_a3i5(
                decode_a3i5(source_help_us.unpack(f"{us_name}.ntft")),
                source_help_us.unpack(f"{us_name}.ntfp"),
            ),
            "CN": render_a3i5(item["pixels"], item["palette"]),
        }
        sheet = Image.new("RGBA", (768, 276), (36, 39, 48, 255))
        draw = ImageDraw.Draw(sheet)
        for column, label in enumerate(("JP", "US", "CN")):
            draw.text((column * 256 + 4, 2), f"{texture_name} / {label}", fill="white")
            sheet.alpha_composite(previews[label], (column * 256, 20))
        preview_path = args.output_dir / f"{texture_name}_JP_US_CN.png"
        sheet.save(preview_path)
        help_previews[texture_name] = str(preview_path)

    source_menu_jp = PackedArchive(source_rom.get_file(DATA_PATH))
    source_menu_us = PackedArchive(source_rom.get_file(DATA_US_PATH))
    menu_previews: dict[str, str] = {}
    for screen_name, item in localized_menu.items():
        us_screen_name = f"{screen_name}US"
        jp_palette = source_menu_jp.unpack(f"{screen_name}.nbfp")
        us_palette = source_menu_us.unpack(f"{us_screen_name}.nbfp")
        previews = {
            "JP": render_nb(
                decode_4bpp_screen(
                    source_menu_jp.unpack(f"{screen_name}.nbfc"),
                    source_menu_jp.unpack(f"{screen_name}.nbfs"),
                ),
                jp_palette,
            ),
            "US": render_nb(
                decode_4bpp_screen(
                    source_menu_us.unpack(f"{us_screen_name}.nbfc"),
                    source_menu_us.unpack(f"{us_screen_name}.nbfs"),
                ),
                us_palette,
            ),
            "CN": render_nb(item["pixels"], item["palette"]),
        }
        height = max(image.height for image in previews.values())
        sheet = Image.new("RGBA", (768, height + 20), (36, 39, 48, 255))
        draw = ImageDraw.Draw(sheet)
        for column, label in enumerate(("JP", "US", "CN")):
            draw.text((column * 256 + 4, 2), f"{screen_name} / {label}", fill="white")
            sheet.alpha_composite(previews[label], (column * 256, 20))
        preview_path = args.output_dir / f"{screen_name}_JP_US_CN.png"
        sheet.save(preview_path)
        menu_previews[screen_name] = str(preview_path)

    report = {
        "help_pages": [
            {
                "texture": texture_name,
                "sections": item["sections"],
                "preview": help_previews[texture_name],
            }
            for texture_name, item in localized_help.items()
        ],
        "data_screens": [
            {
                "screen": screen_name,
                "localized_character_tiles": item["character_tiles"],
                "preview": menu_previews[screen_name],
            }
            for screen_name, item in localized_menu.items()
        ],
        "style_policy": "localized Japanese functional text; preserved stylized English",
        "fonts": {
            "help": str(args.help_bdf),
            "menu_prompt": str(args.menu_bdf),
            "menu_labels": str(args.menu_label_font),
        },
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "changed_from_base": result.changed_from_base,
        "changed_from_source": result.changed_from_source,
        "changed_archive_entries": {"help": help_changes, "data": menu_changes},
        "resource_rom_ranges": {
            HELP_PATH: result.rom_range(HELP_PATH),
            DATA_PATH: result.rom_range(DATA_PATH),
        },
        "output_rom": str(result.rom_path),
        "output_patch": str(result.patch_path),
    }
    write_report(stage, report, "build_report.json")


if __name__ == "__main__":
    main()
