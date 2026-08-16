#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
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
    add_stage_arguments,
    finish_stage,
    load_stage,
    write_report,
)

CLEAR_PATH = "romdata/scene/common/clearevent.bin"
DP_RESOURCE = "message_jp_dp"
BODY_RESOURCES = (
    "message_jp_normal00",
    "message_jp_normal01",
    "message_jp_normal02",
    "message_jp_hard00",
    "message_jp_hard01",
    "message_jp_hard02",
    "message_jp_hell00",
    "message_jp_hell01",
    "message_jp_hell02",
    "message_jp_story_00",
    "message_jp_tutorial00",
    "message_jp_zbattle00",
    "message_jp_zbattle01",
    "message_jp_zbattle02",
)
INFOBAR_IDS = (
    "congratulations",
    "story",
    "storyallcomp",
    "normal",
    "hard",
    "hell",
    "tutorial",
    "zbattle",
)
BODY_RECT = (24, 64, 232, 128)
BODY_COLOR = 10
LINE_HEIGHT = 15
DP_WIDTH = 512
DP_HEIGHT = 32
DP_COLOR = 1
DP_TEXT_HEIGHT = 15
BODY_PALETTE = "message_en_normal00.nbfp"
DP_PALETTE = "message_en_dp.ntfp"
INFOBAR_PALETTE = "infobar_en_congratulations.ntfp"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def text_width(text: str, masks: dict[str, list[list[bool]]]) -> int:
    return sum(len(masks[character][0]) for character in text)


def scale_masks(
    masks: dict[str, list[list[bool]]], target_height: int
) -> dict[str, list[list[bool]]]:
    scaled = {}
    for character, mask in masks.items():
        source_height = len(mask)
        source_width = len(mask[0])
        target_width = max(1, round(source_width * target_height / source_height))
        scaled[character] = [
            [
                mask[min(source_height - 1, y * source_height // target_height)][
                    min(source_width - 1, x * source_width // target_width)
                ]
                for x in range(target_width)
            ]
            for y in range(target_height)
        ]
    return scaled


def clear_rect(
    pixels: list[list[int]], rect: tuple[int, int, int, int], value: int = 0
) -> None:
    x0, y0, x1, y1 = rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            pixels[y][x] = value


def draw_line(
    pixels: list[list[int]],
    text: str,
    masks: dict[str, list[list[bool]]],
    x: int,
    y: int,
    value: int,
) -> None:
    cursor_x = x
    for character in text:
        mask = masks[character]
        for glyph_y, row in enumerate(mask):
            for glyph_x, foreground in enumerate(row):
                if foreground:
                    pixels[y + glyph_y][cursor_x + glyph_x] = value
        cursor_x += len(mask[0])


def replace_block(
    pixels: list[list[int]],
    text: str,
    masks: dict[str, list[list[bool]]],
    rect: tuple[int, int, int, int],
    color: int,
) -> None:
    clear_rect(pixels, rect)
    lines = text.split("\\n")
    widths = [text_width(line, masks) for line in lines]
    block_width = max(widths, default=0)
    glyph_height = max(
        (len(masks[character]) for line in lines for character in line), default=0
    )
    block_height = glyph_height + max(0, len(lines) - 1) * LINE_HEIGHT
    x0, y0, x1, y1 = rect
    if block_width > x1 - x0 or block_height > y1 - y0:
        raise ValueError(f"clear message does not fit {rect}: {text}")
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


def assert_unchanged_outside_rect(
    before: list[list[int]],
    after: list[list[int]],
    rect: tuple[int, int, int, int],
    label: str,
) -> None:
    x0, y0, x1, y1 = rect
    for y, (before_row, after_row) in enumerate(zip(before, after)):
        for x, (old, new) in enumerate(zip(before_row, after_row)):
            if old != new and not (x0 <= x < x1 and y0 <= y < y1):
                raise ValueError(f"pixel outside message changed: {label} at {x},{y}")


def decode_1bpp_linear(data: bytes) -> list[list[int]]:
    values = [(byte >> bit) & 1 for byte in data for bit in range(8)]
    if len(values) != DP_WIDTH * DP_HEIGHT:
        raise ValueError(f"unexpected DP texture size: {len(data)}")
    return [values[y * DP_WIDTH : (y + 1) * DP_WIDTH] for y in range(DP_HEIGHT)]


def encode_1bpp_linear(pixels: list[list[int]]) -> bytes:
    if len(pixels) != DP_HEIGHT or any(len(row) != DP_WIDTH for row in pixels):
        raise ValueError("DP texture must be 512x32")
    values = [value for row in pixels for value in row]
    if any(value not in (0, 1) for value in values):
        raise ValueError("DP texture must be 1bpp")
    output = bytearray(len(values) // 8)
    for index, value in enumerate(values):
        output[index // 8] |= value << (index & 7)
    return bytes(output)


def decode_4bpp_linear(data: bytes, *, width: int = 512) -> list[list[int]]:
    values = [value for byte in data for value in (byte & 0xF, byte >> 4)]
    if len(values) % width:
        raise ValueError("linear 4bpp texture has unexpected size")
    return [values[y * width : (y + 1) * width] for y in range(len(values) // width)]


def render_indexed(
    pixels: list[list[int]], palette_data: bytes, *, transparent_zero: bool = True
) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (len(pixels[0]), len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value or not transparent_zero:
                image.putpixel((x, y), palette[value])
    return image


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
        argparse.ArgumentParser(description="Build localized unlock and clear messages."),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_vs_test/DBZ_Bukuu_Ressen_CN_UI_VSTest.nds",
        table="data/translation/ui_clear_messages.tsv",
        output_dir="build/ui_clear_test",
    )
    args = parser.parse_args()

    rows = read_rows(args.table)
    expected_resources = {DP_RESOURCE, *BODY_RESOURCES}
    resources = {row["resource"] for row in rows}
    if resources != expected_resources or len(rows) != len(expected_resources):
        raise ValueError("clear-message translation rows differ from expected resources")
    by_resource = {row["resource"]: row for row in rows}
    all_characters = "".join(
        row["simplified_chinese"].replace("\\n", "") for row in rows
    )
    stage = load_stage(args, PROJECT_ROOT, characters=all_characters)
    masks = stage.masks
    source_rom = stage.source_rom
    original_data = stage.base_rom.get_file(CLEAR_PATH)
    original = PackedArchive(original_data)
    archive = PackedArchive(original_data)

    before_bodies = {}
    after_bodies = {}
    for resource in BODY_RESOURCES:
        before = decode_4bpp_screen(
            original.unpack(f"{resource}.nbfc"), original.unpack(f"{resource}.nbfs")
        )
        after = [row[:] for row in before]
        replace_block(
            after,
            by_resource[resource]["simplified_chinese"],
            masks,
            BODY_RECT,
            BODY_COLOR,
        )
        assert_unchanged_outside_rect(before, after, BODY_RECT, resource)
        characters, screen = encode_4bpp_screen(after)
        archive.replace_unpacked(f"{resource}.nbfc", characters)
        archive.replace_unpacked(f"{resource}.nbfs", screen)
        before_bodies[resource] = before
        after_bodies[resource] = after

    before_dp = decode_1bpp_linear(original.unpack(f"{DP_RESOURCE}.ntft"))
    after_dp = [row[:] for row in before_dp]
    dp_masks = scale_masks(masks, DP_TEXT_HEIGHT)
    replace_block(
        after_dp,
        by_resource[DP_RESOURCE]["simplified_chinese"],
        dp_masks,
        (0, 0, DP_WIDTH, DP_HEIGHT),
        DP_COLOR,
    )
    archive.replace_unpacked(f"{DP_RESOURCE}.ntft", encode_1bpp_linear(after_dp))

    rebuilt_data = archive.build()
    rebuilt = PackedArchive(rebuilt_data)
    for resource in BODY_RESOURCES:
        actual = decode_4bpp_screen(
            rebuilt.unpack(f"{resource}.nbfc"), rebuilt.unpack(f"{resource}.nbfs")
        )
        if actual != after_bodies[resource]:
            raise ValueError(f"rebuilt clear message failed validation: {resource}")
    if decode_1bpp_linear(rebuilt.unpack(f"{DP_RESOURCE}.ntft")) != after_dp:
        raise ValueError("rebuilt DP message failed validation")
    expected_changes = {f"{DP_RESOURCE}.ntft"} | {
        f"{resource}.{extension}"
        for resource in BODY_RESOURCES
        for extension in ("nbfc", "nbfs")
    }
    actual_changes = set(changed_entries(original, rebuilt))
    if actual_changes != expected_changes:
        raise ValueError(
            f"unexpected clear-event archive changes: {sorted(actual_changes ^ expected_changes)}"
        )

    result = finish_stage(
        stage,
        {CLEAR_PATH: rebuilt_data},
        rom_name="DBZ_Bukuu_Ressen_CN_UI_ClearTest",
        metadata=b"DBZ BR CN clear messages",
        resource_names={CLEAR_PATH: "clearevent_CN.bin"},
    )
    output_bytes = result.output_bytes

    source_archive = PackedArchive(source_rom.get_file(CLEAR_PATH))
    body_palette = source_archive.unpack(BODY_PALETTE)
    sheet = Image.new("RGBA", (768, len(BODY_RESOURCES) * 100), (36, 39, 48, 255))
    draw = ImageDraw.Draw(sheet)
    for row_index, resource in enumerate(BODY_RESOURCES):
        y = row_index * 100
        draw.text((4, y + 2), resource.removeprefix("message_jp_"), fill="white")
        english = resource.replace("message_jp_", "message_en_")
        sources = {
            "JP": before_bodies[resource],
            "US": decode_4bpp_screen(
                source_archive.unpack(f"{english}.nbfc"),
                source_archive.unpack(f"{english}.nbfs"),
            ),
            "CN": after_bodies[resource],
        }
        for column, (label, pixels) in enumerate(sources.items()):
            draw.text((column * 256 + 224, y + 2), label, fill="white")
            image = render_indexed(pixels, body_palette).crop((0, 56, 256, 136))
            sheet.alpha_composite(image, (column * 256, y + 20))
    body_preview = args.output_dir / "messages_JP_US_CN.png"
    sheet.save(body_preview)

    dp_palette = source_archive.unpack(DP_PALETTE)
    dp_sheet = Image.new("RGBA", (DP_WIDTH * 3, DP_HEIGHT + 20), (36, 39, 48, 255))
    dp_draw = ImageDraw.Draw(dp_sheet)
    dp_sources = {
        "JP": before_dp,
        "US": decode_1bpp_linear(source_archive.unpack("message_en_dp.ntft")),
        "CN": after_dp,
    }
    for column, (label, pixels) in enumerate(dp_sources.items()):
        dp_draw.text((column * DP_WIDTH + 4, 2), label, fill="white")
        dp_sheet.alpha_composite(render_indexed(pixels, dp_palette), (column * DP_WIDTH, 20))
    dp_preview = args.output_dir / "dp_message_JP_US_CN.png"
    dp_sheet.save(dp_preview)

    infobar_palette = source_archive.unpack(INFOBAR_PALETTE)
    bar_sheet = Image.new("RGBA", (1024, len(INFOBAR_IDS) * 52), (36, 39, 48, 255))
    bar_draw = ImageDraw.Draw(bar_sheet)
    for row_index, item in enumerate(INFOBAR_IDS):
        y = row_index * 52
        bar_draw.text((4, y + 2), item, fill="white")
        for column, language in enumerate(("jp", "en")):
            pixels = decode_4bpp_linear(
                source_archive.unpack(f"infobar_{language}_{item}.ntft")
            )
            bar_sheet.alpha_composite(
                render_indexed(pixels, infobar_palette, transparent_zero=False),
                (column * 512, y + 20),
            )
    bar_preview = args.output_dir / "preserved_infobars_JP_US.png"
    bar_sheet.save(bar_preview)

    report = {
        "localized_messages": len(rows),
        "localized_body_screens": len(BODY_RESOURCES),
        "localized_small_textures": [f"{DP_RESOURCE}.ntft"],
        "preserved_stylized_infobars": [
            f"infobar_jp_{item}.ntft" for item in INFOBAR_IDS
        ],
        "font": str(args.bdf),
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "changed_from_base": result.changed_from_base,
        "changed_from_source": result.changed_from_source,
        "changed_archive_entries": sorted(actual_changes),
        "resource_rom_range": [result.replaced[0].start, result.replaced[0].end],
        "previews": [str(body_preview), str(dp_preview), str(bar_preview)],
        "output_resource": str(result.resource_paths[0]),
        "output_rom": str(result.rom_path),
        "output_patch": str(result.patch_path),
    }
    write_report(stage, report)


if __name__ == "__main__":
    main()
