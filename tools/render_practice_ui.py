#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nds import NDSRom
from dbzbr.nitro_bg import decode_4bpp_tile, decode_bgr555_palette

TUTORIAL_PATH = "romdata/scene/common/tutorial.bin"
PRACTICE_SELECT_PATH = "romdata/scene/common/prcselect.bin"
TUTORIAL_TOPICS = (
    "move",
    "attack",
    "gard",
    "support",
    "change",
    "aura",
    "hdash",
    "barrier",
    "throw",
    "bullet",
    "reflect",
    "special",
    "killer",
    "fight",
    "union",
)


def render_nb(
    archive: PackedArchive,
    character_name: str,
    screen_name: str,
    palette_name: str,
) -> Image.Image:
    characters = archive.unpack(character_name)
    screen = archive.unpack(screen_name)
    if len(characters) % 32 or len(screen) % 64:
        raise ValueError(f"invalid NB resource: {character_name}, {screen_name}")
    values = struct.unpack(f"<{len(screen) // 2}H", screen)
    height = len(values) // 32 * 8
    palette = decode_bgr555_palette(archive.unpack(palette_name))
    image = Image.new("RGBA", (256, height), palette[0])
    tile_count = len(characters) // 32
    for map_index, value in enumerate(values):
        tile_index = value & 0x3FF
        if tile_index >= tile_count:
            raise ValueError(f"tile {tile_index} exceeds {tile_count}: {character_name}")
        tile = decode_4bpp_tile(characters, tile_index)
        hflip = bool(value & 0x400)
        vflip = bool(value & 0x800)
        palette_bank = value >> 12
        origin_x = map_index % 32 * 8
        origin_y = map_index // 32 * 8
        for y in range(8):
            for x in range(8):
                sx = 7 - x if hflip else x
                sy = 7 - y if vflip else y
                index = palette_bank * 16 + tile[sy][sx]
                image.putpixel((origin_x + x, origin_y + y), palette[index])
    return image


def decode_4bpp_linear(
    texture: bytes,
    palette_data: bytes,
    *,
    palette_bank: int,
    width: int = 256,
) -> Image.Image:
    if len(texture) * 2 % width:
        raise ValueError("4bpp texture does not fit the selected width")
    palette = decode_bgr555_palette(palette_data)
    height = len(texture) * 2 // width
    bank = palette[palette_bank * 16 : (palette_bank + 1) * 16]
    if len(bank) < 16:
        raise ValueError(f"palette bank {palette_bank} is incomplete")
    image = Image.new("RGBA", (width, height), bank[0])
    for byte_index, value in enumerate(texture):
        pixel_index = byte_index * 2
        image.putpixel((pixel_index % width, pixel_index // width), bank[value & 0x0F])
        pixel_index += 1
        image.putpixel((pixel_index % width, pixel_index // width), bank[value >> 4])
    return image


def save_pair(
    output_dir: Path,
    name: str,
    jp: Image.Image,
    en: Image.Image,
) -> str:
    width = max(jp.width, en.width)
    height = max(jp.height, en.height)
    sheet = Image.new("RGBA", (width * 2, height + 20), (36, 39, 48, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((4, 2), f"{name} / JP", fill="white")
    draw.text((width + 4, 2), f"{name} / EN", fill="white")
    sheet.alpha_composite(jp, (0, 20))
    sheet.alpha_composite(en, (width, 20))
    path = output_dir / f"{name}_JP_EN.png"
    sheet.save(path)
    return str(path)


def archive_inventory(archive: PackedArchive) -> list[dict[str, object]]:
    return [
        {
            "index": index,
            "name": entry.name,
            "unpacked_size": entry.unpacked_size,
            "packed_size": entry.packed_size,
            "compression": f"0x{entry.packed_data[0]:02x}",
        }
        for index, entry in enumerate(archive.entries)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Render practice-mode Japanese and English UI assets.")
    parser.add_argument(
        "--rom",
        type=Path,
        default=PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "build/practice_ui_audit",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rom = NDSRom.from_file(args.rom)
    tutorial = PackedArchive(rom.get_file(TUTORIAL_PATH))
    practice = PackedArchive(rom.get_file(PRACTICE_SELECT_PATH))
    previews: dict[str, str] = {}

    tutorial_palette = "tutorial_en_move.nbfp"
    for topic in TUTORIAL_TOPICS:
        images = {}
        for language in ("jp", "en"):
            stem = f"tutorial_{language}_{topic}"
            images[language] = render_nb(
                tutorial,
                f"{stem}.nbfc",
                f"{stem}.nbfs",
                tutorial_palette,
            )
        previews[f"tutorial_{topic}"] = save_pair(
            args.output_dir,
            f"tutorial_{topic}",
            images["jp"],
            images["en"],
        )

    practice_palette = "prc_jp_doc00.nbfp"
    for doc_id in ("doc00", "doc01"):
        images = {}
        for language in ("jp", "en"):
            stem = f"prc_{language}_{doc_id}"
            images[language] = render_nb(
                practice,
                f"{stem}.nbfc",
                f"{stem}.nbfs",
                practice_palette,
            )
        previews[f"practice_{doc_id}"] = save_pair(
            args.output_dir,
            f"practice_{doc_id}",
            images["jp"],
            images["en"],
        )

    # The three labels share a 48-color palette: one 16-color bank per label.
    select_palette_names = {"jp": "prc_jp_select.ntfp", "en": "prc_en_select.ntfp"}
    for bank, label in enumerate(("course", "training", "tutorial")):
        images = {}
        for language in ("jp", "en"):
            images[language] = decode_4bpp_linear(
                practice.unpack(f"prc_{language}_{label}.ntft"),
                practice.unpack(select_palette_names[language]),
                palette_bank=bank,
            )
        previews[f"practice_{label}"] = save_pair(
            args.output_dir,
            f"practice_{label}",
            images["jp"],
            images["en"],
        )

    report = {
        "rom_sha256": rom.sha256,
        "resource_paths": [TUTORIAL_PATH, PRACTICE_SELECT_PATH],
        "tutorial_inventory": archive_inventory(tutorial),
        "practice_select_inventory": archive_inventory(practice),
        "previews": previews,
    }
    report_path = args.output_dir / "audit.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
