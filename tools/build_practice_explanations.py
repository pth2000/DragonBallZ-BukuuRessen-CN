#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.font import centered_text_block_origin
from dbzbr.nitro_bg import decode_4bpp_screen, decode_bgr555_palette, encode_4bpp_screen
from dbzbr.uistage import (
    add_stage_arguments,
    finish_stage,
    load_stage,
    write_report,
)

TUTORIAL_PATH = "romdata/scene/common/tutorial.bin"
PRACTICE_SELECT_PATH = "romdata/scene/common/prcselect.bin"
TUTORIAL_PALETTE = "tutorial_en_move.nbfp"
PRACTICE_PALETTE = "prc_jp_doc00.nbfp"
PRACTICE_SELECT_PALETTE = "prc_jp_select.ntfp"
# The original practice/tutorial copy is visually anchored near (127, 103).
# Account for the in-game tilemap offset while retaining a generous clear area.
BODY_RECT = (20, 68, 236, 140)
LINE_HEIGHT = 15
BODY_INDEX = 7
PRESERVED_LABEL_IDS = {"course", "training", "tutorial"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def clear_rect(pixels: list[list[int]], rect: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = rect
    for y in range(y0, y1):
        for x in range(x0, x1):
            pixels[y][x] = 0


def text_width(text: str, masks: dict[str, list[list[bool]]]) -> int:
    return sum(len(masks[character][0]) for character in text)


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


def replace_text(
    pixels: list[list[int]],
    body: str,
    masks: dict[str, list[list[bool]]],
) -> list[list[int]]:
    output = [row[:] for row in pixels]
    clear_rect(output, BODY_RECT)

    lines = body.split("\\n")
    widths = [text_width(line, masks) for line in lines]
    block_width = max(widths, default=0)
    body_height = max(
        (len(masks[character]) for line in lines for character in line), default=0
    )
    block_height = body_height + max(0, len(lines) - 1) * LINE_HEIGHT
    x0, y0, x1, y1 = BODY_RECT
    if block_width > x1 - x0:
        raise ValueError(f"practice body is too wide: {body}")
    if block_height > y1 - y0:
        raise ValueError(f"practice body is too tall: {body}")
    block_x, start_y = centered_text_block_origin(
        BODY_RECT, lines, masks, LINE_HEIGHT
    )
    for line_index, line in enumerate(lines):
        draw_line(output, line, masks, block_x, start_y + line_index * LINE_HEIGHT, BODY_INDEX)
    return output


def decode_4bpp_texture(data: bytes, *, width: int = 256) -> list[list[int]]:
    if len(data) * 2 % width:
        raise ValueError("4bpp texture does not fit the selected width")
    height = len(data) * 2 // width
    values = [value for byte in data for value in (byte & 0x0F, byte >> 4)]
    return [values[y * width : (y + 1) * width] for y in range(height)]


def unpack_screen(
    archive: PackedArchive,
    character_name: str,
    screen_name: str,
    palette_name: str,
) -> tuple[list[list[int]], bytes]:
    return (
        decode_4bpp_screen(archive.unpack(character_name), archive.unpack(screen_name)),
        archive.unpack(palette_name),
    )


def indexed_image(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (256, len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def indexed_texture_image(
    pixels: list[list[int]], palette_data: bytes, palette_bank: int
) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)[palette_bank * 16 : (palette_bank + 1) * 16]
    image = Image.new("RGBA", (len(pixels[0]), len(pixels)), (36, 39, 48, 255))
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
        argparse.ArgumentParser(
            description="Build localized practice and tutorial explanations."
        ),
        project_root=PROJECT_ROOT,
        base_rom="build/ui_stage_test/DBZ_Bukuu_Ressen_CN_UI_StageTest.nds",
        table="data/translation/ui_practice_explanations.tsv",
        output_dir="build/ui_practice_test",
    )
    args = parser.parse_args()

    rows = read_rows(args.table)
    label_rows = [{"id": entry_id} for entry_id in sorted(PRESERVED_LABEL_IDS)]
    expected = {("practice", "doc00"), ("practice", "doc01")}
    expected.update(("tutorial", topic) for topic in (
        "move", "attack", "gard", "support", "change", "aura", "hdash", "barrier",
        "throw", "bullet", "reflect", "special", "killer", "fight", "union",
    ))
    actual = {(row["group"], row["id"]) for row in rows}
    if actual != expected:
        raise ValueError(f"practice table entries differ: missing={expected-actual}, extra={actual-expected}")
    if {row["id"] for row in label_rows} != PRESERVED_LABEL_IDS:
        raise ValueError("practice label table entries differ from expected labels")

    all_characters = "".join(
        row["body_chinese"].replace("\\n", "") for row in rows
    )
    stage = load_stage(args, PROJECT_ROOT, characters=all_characters)
    masks = stage.masks
    source_rom = stage.source_rom
    original_tutorial_resource = stage.base_rom.get_file(TUTORIAL_PATH)
    original_practice_resource = stage.base_rom.get_file(PRACTICE_SELECT_PATH)
    tutorial = PackedArchive(original_tutorial_resource)
    practice = PackedArchive(original_practice_resource)
    original_archives = {
        "tutorial": PackedArchive(original_tutorial_resource),
        "practice": PackedArchive(original_practice_resource),
    }
    localized: dict[tuple[str, str], dict[str, object]] = {}
    localized_labels: dict[str, list[list[int]]] = {}

    for row in rows:
        group = row["group"]
        entry_id = row["id"]
        if group == "tutorial":
            archive = tutorial
            stem = f"tutorial_jp_{entry_id}"
            palette_name = TUTORIAL_PALETTE
        else:
            archive = practice
            stem = f"prc_jp_{entry_id}"
            palette_name = PRACTICE_PALETTE
        pixels, palette = unpack_screen(
            archive, f"{stem}.nbfc", f"{stem}.nbfs", palette_name
        )
        replacement = replace_text(
            pixels, row["body_chinese"], masks
        )
        x0, y0, x1, y1 = BODY_RECT
        if any(
            replacement[y][x] != pixels[y][x]
            for y in range(len(pixels))
            for x in range(len(pixels[y]))
            if not (x0 <= x < x1 and y0 <= y < y1)
        ):
            raise ValueError(f"pixels outside the body changed: {group}/{entry_id}")
        characters, screen = encode_4bpp_screen(replacement)
        archive.replace_unpacked(f"{stem}.nbfc", characters)
        archive.replace_unpacked(f"{stem}.nbfs", screen)
        localized[(group, entry_id)] = {
            "pixels": replacement,
            "palette": palette,
            "character_tiles": len(characters) // 32,
        }

    for row in label_rows:
        entry_id = row["id"]
        texture_name = f"prc_jp_{entry_id}.ntft"
        localized_labels[entry_id] = decode_4bpp_texture(practice.unpack(texture_name))

    rebuilt_tutorial_resource = tutorial.build()
    rebuilt_practice_resource = practice.build()
    result = finish_stage(
        stage,
        {
            TUTORIAL_PATH: rebuilt_tutorial_resource,
            PRACTICE_SELECT_PATH: rebuilt_practice_resource,
        },
        rom_name="DBZ_Bukuu_Ressen_CN_UI_PracticeTest",
        metadata=b"DBZ BR CN practice explanations",
        resource_names={
            TUTORIAL_PATH: "tutorial_CN.bin",
            PRACTICE_SELECT_PATH: "prcselect_CN.bin",
        },
    )
    output_bytes = result.output_bytes

    rebuilt_archives = {
        "tutorial": PackedArchive(rebuilt_tutorial_resource),
        "practice": PackedArchive(rebuilt_practice_resource),
    }
    for row in rows:
        group = row["group"]
        entry_id = row["id"]
        archive = rebuilt_archives[group]
        if group == "tutorial":
            stem = f"tutorial_jp_{entry_id}"
            palette_name = TUTORIAL_PALETTE
        else:
            stem = f"prc_jp_{entry_id}"
            palette_name = PRACTICE_PALETTE
        pixels, palette = unpack_screen(
            archive, f"{stem}.nbfc", f"{stem}.nbfs", palette_name
        )
        expected_item = localized[(group, entry_id)]
        if pixels != expected_item["pixels"] or palette != expected_item["palette"]:
            raise ValueError(f"rebuilt practice screen failed validation: {group}/{entry_id}")
    for row in label_rows:
        entry_id = row["id"]
        rebuilt_pixels = decode_4bpp_texture(
            rebuilt_archives["practice"].unpack(f"prc_jp_{entry_id}.ntft")
        )
        if rebuilt_pixels != localized_labels[entry_id]:
            raise ValueError(f"rebuilt practice label failed validation: {entry_id}")

    changed_by_archive = {
        group: changed_entries(original_archives[group], rebuilt_archives[group])
        for group in ("tutorial", "practice")
    }
    expected_tutorial_names = {
        f"tutorial_jp_{row['id']}.{extension}"
        for row in rows if row["group"] == "tutorial"
        for extension in ("nbfc", "nbfs")
    }
    expected_practice_names = {
        f"prc_jp_{row['id']}.{extension}"
        for row in rows if row["group"] == "practice"
        for extension in ("nbfc", "nbfs")
    }
    if {item["name"] for item in changed_by_archive["tutorial"]} != expected_tutorial_names:
        raise ValueError("unexpected tutorial archive changes")
    if {item["name"] for item in changed_by_archive["practice"]} != expected_practice_names:
        raise ValueError("unexpected practice-select archive changes")

    source_archives = {
        "tutorial": PackedArchive(source_rom.get_file(TUTORIAL_PATH)),
        "practice": PackedArchive(source_rom.get_file(PRACTICE_SELECT_PATH)),
    }
    preview_paths: dict[str, str] = {}
    sheet = Image.new("RGBA", (768, len(rows) * 212), (36, 39, 48, 255))
    sheet_draw = ImageDraw.Draw(sheet)
    for row_index, row in enumerate(rows):
        group = row["group"]
        entry_id = row["id"]
        if group == "tutorial":
            source_archive = source_archives[group]
            jp_stem = f"tutorial_jp_{entry_id}"
            en_stem = f"tutorial_en_{entry_id}"
            palette_name = TUTORIAL_PALETTE
        else:
            source_archive = source_archives[group]
            jp_stem = f"prc_jp_{entry_id}"
            en_stem = f"prc_en_{entry_id}"
            palette_name = PRACTICE_PALETTE
        jp_pixels, jp_palette = unpack_screen(
            source_archive, f"{jp_stem}.nbfc", f"{jp_stem}.nbfs", palette_name
        )
        en_pixels, en_palette = unpack_screen(
            source_archive, f"{en_stem}.nbfc", f"{en_stem}.nbfs", palette_name
        )
        previews = {
            "JP": indexed_image(jp_pixels, jp_palette),
            "EN": indexed_image(en_pixels, en_palette),
            "CN": indexed_image(
                localized[(group, entry_id)]["pixels"],
                localized[(group, entry_id)]["palette"],
            ),
        }
        entry_sheet = Image.new("RGBA", (768, 212), (36, 39, 48, 255))
        entry_draw = ImageDraw.Draw(entry_sheet)
        for column, label in enumerate(("JP", "EN", "CN")):
            caption = f"{group}/{entry_id} / {label}"
            entry_draw.text((column * 256 + 4, 2), caption, fill="white")
            entry_sheet.alpha_composite(previews[label], (column * 256, 20))
            sheet_draw.text((column * 256 + 4, row_index * 212 + 2), caption, fill="white")
            sheet.alpha_composite(previews[label], (column * 256, row_index * 212 + 20))
        entry_path = args.output_dir / f"{group}_{entry_id}_JP_EN_CN.png"
        entry_sheet.save(entry_path)
        preview_paths[f"{group}/{entry_id}"] = str(entry_path)
    preview_path = args.output_dir / "all_JP_EN_CN.png"
    sheet.save(preview_path)

    label_previews: dict[str, str] = {}
    select_palette = source_archives["practice"].unpack(PRACTICE_SELECT_PALETTE)
    rebuilt_select_palette = rebuilt_archives["practice"].unpack(PRACTICE_SELECT_PALETTE)
    for palette_bank, row in enumerate(label_rows):
        entry_id = row["id"]
        jp_pixels = decode_4bpp_texture(
            source_archives["practice"].unpack(f"prc_jp_{entry_id}.ntft")
        )
        en_pixels = decode_4bpp_texture(
            source_archives["practice"].unpack(f"prc_en_{entry_id}.ntft")
        )
        previews = {
            "JP": indexed_texture_image(jp_pixels, select_palette, palette_bank),
            "EN": indexed_texture_image(en_pixels, select_palette, palette_bank),
            "CN": indexed_texture_image(
                localized_labels[entry_id], rebuilt_select_palette, palette_bank
            ),
        }
        height = max(image.height for image in previews.values())
        label_sheet = Image.new("RGBA", (768, height + 20), (36, 39, 48, 255))
        label_draw = ImageDraw.Draw(label_sheet)
        for column, label in enumerate(("JP", "EN", "CN")):
            label_draw.text((column * 256 + 4, 2), f"label/{entry_id} / {label}", fill="white")
            label_sheet.alpha_composite(previews[label], (column * 256, 20))
        label_path = args.output_dir / f"label_{entry_id}_JP_EN_CN.png"
        label_sheet.save(label_path)
        label_previews[entry_id] = str(label_path)

    report = {
        "entries": [
            {
                "group": row["group"],
                "id": row["id"],
                "title_art": "preserved original graphic",
                "body": row["body_chinese"],
                "localized_character_tiles": localized[(row["group"], row["id"])][
                    "character_tiles"
                ],
                "preview": preview_paths[f"{row['group']}/{row['id']}"],
            }
            for row in rows
        ],
        "labels": [
            {
                "id": row["id"],
                "label_art": "preserved original graphic",
                "preview": label_previews[row["id"]],
            }
            for row in label_rows
        ],
        "layout": {
            "body_rect": BODY_RECT,
            "line_height": LINE_HEIGHT,
            "title": "preserved original graphic",
            "body_alignment": "left within centered text block",
        },
        "font_bdf": str(args.bdf),
        "base_rom_sha256": hashlib.sha256(stage.base_bytes).hexdigest(),
        "output_rom_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "patch_sha256": hashlib.sha256(result.patch).hexdigest(),
        "changed_from_base": result.changed_from_base,
        "changed_from_source": result.changed_from_source,
        "changed_archive_entries": changed_by_archive,
        "resource_rom_ranges": {
            TUTORIAL_PATH: result.rom_range(TUTORIAL_PATH),
            PRACTICE_SELECT_PATH: result.rom_range(PRACTICE_SELECT_PATH),
        },
        "output_rom": str(result.rom_path),
        "output_patch": str(result.patch_path),
        "preview": str(preview_path),
    }
    write_report(stage, report, "build_report.json")


if __name__ == "__main__":
    main()
