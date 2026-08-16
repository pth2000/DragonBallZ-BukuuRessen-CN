#!/usr/bin/env python3
"""Render the curated Japanese/English/Chinese story comparison strips.

Japanese and Chinese are read out of the two ROMs at the same script location,
so a strip shows what the game actually draws. English comes from the sample
table because regional scripts do not share block or command numbering.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.bps import apply_patch
from dbzbr.nds import NDSRom
from dbzbr.showcase import RomFonts, build_panels, render_strip, render_texture, stack_textures


def read_samples(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> None:
    config = json.loads((PROJECT_ROOT / "project.json").read_text(encoding="utf-8"))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-rom",
        type=Path,
        default=PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds",
        help="Original ADBJ Rev 0 ROM",
    )
    parser.add_argument(
        "--patched-rom",
        type=Path,
        help="Already patched ROM; when omitted the patch is applied in memory",
    )
    parser.add_argument(
        "--patch",
        type=Path,
        default=PROJECT_ROOT / "dist" / config["release_patch_name"],
        help="Release BPS used when --patched-rom is not given",
    )
    parser.add_argument(
        "--samples", type=Path, default=PROJECT_ROOT / "data/showcase/story_samples.tsv"
    )
    parser.add_argument(
        "--ui-samples", type=Path, default=PROJECT_ROOT / "data/showcase/ui_samples.tsv"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "docs/assets/showcase"
    )
    parser.add_argument("--scale", type=int, default=3)
    parser.add_argument(
        "--columns",
        type=int,
        default=24,
        help="Wrap width in full-width characters",
    )
    args = parser.parse_args()

    if not args.source_rom.is_file():
        raise SystemExit(f"missing source ROM: {args.source_rom}")

    if args.patched_rom:
        patched_path = args.patched_rom
        if not patched_path.is_file():
            raise SystemExit(f"missing patched ROM: {patched_path}")
        patched_bytes = patched_path.read_bytes()
    else:
        if not args.patch.is_file():
            raise SystemExit(
                f"missing release patch: {args.patch}\n"
                "pass --patched-rom, or build the release first"
            )
        patched_bytes = apply_patch(args.source_rom.read_bytes(), args.patch.read_bytes())
        patched_path = args.output_dir.parent / ".showcase_patched.nds"
        patched_path.parent.mkdir(parents=True, exist_ok=True)
        patched_path.write_bytes(patched_bytes)

    original = RomFonts.load(args.source_rom, config["script_path"], config["font_path"])
    patched = RomFonts.load(patched_path, config["script_path"], config["font_path"])

    rendered = []
    for row in read_samples(args.samples):
        panels = build_panels(
            original,
            patched,
            row["script"],
            int(row["block"]),
            int(row["command"]),
            english=row.get("english") or None,
            max_width=args.columns * 15,
        )
        name = f"story-{int(row['id']):04d}-{row['script']}.png"
        output = render_strip(panels, args.output_dir / name, scale=args.scale)
        rendered.append(output)
        print(f"{row['id']:>5}  {row['script']}  {output.relative_to(PROJECT_ROOT).as_posix()}")

    # UI textures are the artwork the game draws directly, so pulling one from the
    # patched ROM shows the finished Chinese screen rather than a font mock-up.
    original_rom = original.rom
    patched_rom = NDSRom(patched_bytes)
    for row in read_samples(args.ui_samples):
        width = int(row["width"])
        images = [
            render_texture(original_rom, row["archive"], row["texture"], row["palette"], width=width),
            render_texture(
                original_rom, row["en_archive"], row["en_texture"], row["en_palette"], width=width
            ),
            render_texture(patched_rom, row["archive"], row["texture"], row["palette"], width=width),
        ]
        output = stack_textures(
            images, args.output_dir / f"ui-{row['id']}.png", labels=["JP", "EN", "CN"]
        )
        rendered.append(output)
        print(f"  ui   {row['id']}  {output.relative_to(PROJECT_ROOT).as_posix()}")

    if not args.patched_rom:
        patched_path.unlink(missing_ok=True)
    print(f"\n{len(rendered)} images -> {args.output_dir.relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
