#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.build import TextEncoder, load_existing_assignments
from dbzbr.font import GameFont, find_font_map
from dbzbr.nds import NDSRom
from dbzbr.preview import render_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Render text with the ROM's real 2bpp font.")
    parser.add_argument("rom", type=Path)
    parser.add_argument("text", help=r"Use literal \n for a line break")
    parser.add_argument("--map", type=Path, default=PROJECT_ROOT / "data/mapping/custom_glyph_map.tsv")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "build/text_preview.png")
    parser.add_argument("--columns", type=int, default=24)
    parser.add_argument("--scale", type=int, default=3)
    args = parser.parse_args()
    config = json.loads((PROJECT_ROOT / "project.json").read_text(encoding="utf-8"))
    rom = NDSRom.from_file(args.rom)
    _, entries = find_font_map(rom.arm9())
    by_code = {entry.code: entry for entry in entries}
    assignments = load_existing_assignments(args.map, by_code)
    encoder = TextEncoder(by_code, assignments)
    font = GameFont(rom.get_file(config["font_path"]))
    render_text(args.text, encoder, font, by_code, args.output, max_columns=args.columns, scale=args.scale)
    print(args.output)


if __name__ == "__main__":
    main()
