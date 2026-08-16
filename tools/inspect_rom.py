#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.archive import PackedArchive
from dbzbr.font import find_font_map
from dbzbr.nds import NDSRom

FONT_MAP_HEADERS = (
    "index",
    "arm9_relative_offset",
    "page",
    "code_hex",
    "native_character",
    "x0",
    "y0",
    "x1",
    "y1",
    "width",
    "height",
)


def dump_font_map(offset: int, entries, output: Path) -> None:
    """Write the ARM9 code-to-rectangle table as a TSV.

    The build reads this table straight from the ROM; the checked-in copy at
    data/mapping/arm9_font_map.tsv exists only as a reference for format work,
    and this regenerates it from any matching ROM.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(FONT_MAP_HEADERS)
        for index, entry in enumerate(entries):
            writer.writerow(
                [
                    index,
                    f"{offset + index * 12:08X}",
                    entry.page,
                    f"{entry.code:04X}",
                    entry.native_character,
                    entry.x0,
                    entry.y0,
                    entry.x1,
                    entry.y1,
                    entry.width,
                    entry.height,
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Show the ROM and custom resource structure.")
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--dump-font-map",
        type=Path,
        nargs="?",
        const=PROJECT_ROOT / "data/mapping/arm9_font_map.tsv",
        help="Also write the ARM9 font map as TSV (default: the checked-in copy)",
    )
    args = parser.parse_args()
    rom = NDSRom.from_file(args.rom)
    script = PackedArchive(rom.get_file("romdata/scene/script.bin"))
    font = PackedArchive(rom.get_file("romdata/scene/font_jp.bin"))
    offset, entries = find_font_map(rom.arm9())
    result = {
        "game_code": rom.game_code,
        "version": rom.rom_version,
        "sha256": rom.sha256,
        "files": len(rom.list_files()),
        "script_archive_entries": len(script.entries),
        "script_names": script.names(),
        "font_archive_entries": len(font.entries),
        "font_names": font.names(),
        "font_map_arm9_relative_offset": f"0x{offset:X}",
        "font_map_entries": len(entries),
    }
    if args.dump_font_map:
        dump_font_map(offset, entries, args.dump_font_map)
        result["font_map_dump"] = str(args.dump_font_map)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
