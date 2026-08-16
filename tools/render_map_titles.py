#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from PIL import Image, ImageDraw

from dbzbr.archive import PackedArchive
from dbzbr.nds import NDSRom
from dbzbr.nitro_bg import decode_bgr555_palette

JP_PATH = "romdata/scene/maptitle_jp_tex.bin"
EN_PATH = "romdata/scene/maptitle_en_tex.bin"


def decode_4bpp_linear(data: bytes, *, width: int = 256) -> list[list[int]]:
    if len(data) * 2 % width:
        raise ValueError("4bpp texture does not fit the selected width")
    values = [value for byte in data for value in (byte & 0x0F, byte >> 4)]
    height = len(values) // width
    return [values[y * width : (y + 1) * width] for y in range(height)]


def render(pixels: list[list[int]], palette_data: bytes) -> Image.Image:
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (len(pixels[0]), len(pixels)), (36, 39, 48, 255))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Japanese/English story map titles.")
    parser.add_argument(
        "--rom",
        type=Path,
        default=PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "build/map_title_audit"
    )
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()
    if args.scale < 1:
        raise ValueError("scale must be at least 1")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rom = NDSRom.from_file(args.rom)
    archives = {
        "JP": PackedArchive(rom.get_file(JP_PATH)),
        "EN": PackedArchive(rom.get_file(EN_PATH)),
    }
    routes = sorted(
        {
            name.split("_")[1]
            for name in archives["JP"].names()
            if name.startswith("titlebar_") and name.endswith("_00.ntfp")
        }
    )
    report_routes = []
    for route in routes:
        sheet = Image.new("RGBA", (512, 5 * 84), (36, 39, 48, 255))
        draw = ImageDraw.Draw(sheet)
        frames = []
        for frame_index in range(5):
            frame = f"{frame_index:02d}"
            texture_name = f"titlebar_{route}_{frame}.ntft"
            palette_name = f"titlebar_{route}_00.ntfp"
            images = {}
            unpacked = {}
            for label, archive in archives.items():
                unpacked[label] = archive.unpack(texture_name)
                images[label] = render(
                    decode_4bpp_linear(unpacked[label]), archive.unpack(palette_name)
                )
            y = frame_index * 84
            for column, label in enumerate(("JP", "EN")):
                draw.text((column * 256 + 4, y + 2), f"{route}/{frame} / {label}", fill="white")
                sheet.alpha_composite(images[label], (column * 256, y + 20))
            frames.append(
                {
                    "frame": frame,
                    "same_decompressed_texture": unpacked["JP"] == unpacked["EN"],
                }
            )
        output = args.output_dir / f"{route}_JP_EN.png"
        if args.scale > 1:
            sheet = sheet.resize(
                (sheet.width * args.scale, sheet.height * args.scale),
                Image.Resampling.NEAREST,
            )
        sheet.save(output)
        report_routes.append({"route": route, "frames": frames, "preview": str(output)})

    report = {
        "rom_sha256": rom.sha256,
        "resource_paths": {"JP": JP_PATH, "EN": EN_PATH},
        "routes": report_routes,
    }
    report_path = args.output_dir / "audit.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
