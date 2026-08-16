#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.archive import ArchiveError, PackedArchive
from dbzbr.nds import NDSRom


def suffix_counts(names: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(Path(name).suffix.lower() or "<none>" for name in names).items()))


def normalized_name(name: str) -> str:
    return (
        name.replace("_JA.", "_XX.")
        .replace("_US.", "_XX.")
        .replace("JA.", "XX.")
        .replace("US.", "XX.")
    )


def inspect_archive(data: bytes) -> dict[str, object]:
    archive = PackedArchive(data)
    names = archive.names()
    unique_names = list(dict.fromkeys(names))
    return {
        "entry_count": len(names),
        "unique_entry_count": len(unique_names),
        "suffix_counts": suffix_counts(names),
        "unique_names": unique_names,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory paired JA/US UI archives.")
    parser.add_argument(
        "rom",
        type=Path,
        nargs="?",
        default=PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "build/regional_ui_audit.json",
    )
    args = parser.parse_args()

    rom = NDSRom.from_file(args.rom)
    paths = {entry.path for entry in rom.list_files()}
    report: list[dict[str, object]] = []
    for ja_path in sorted(path for path in paths if path.endswith("JA.bin")):
        us_path = ja_path[:-6] + "US.bin"
        if us_path not in paths:
            continue
        item: dict[str, object] = {
            "ja_path": ja_path,
            "us_path": us_path,
            "ja_size": len(rom.get_file(ja_path)),
            "us_size": len(rom.get_file(us_path)),
        }
        try:
            ja = inspect_archive(rom.get_file(ja_path))
            us = inspect_archive(rom.get_file(us_path))
            item["ja_archive"] = ja
            item["us_archive"] = us
            ja_normalized = {normalized_name(name) for name in ja["unique_names"]}
            us_normalized = {normalized_name(name) for name in us["unique_names"]}
            item["normalized_name_overlap"] = sorted(ja_normalized & us_normalized)
            item["ja_only_normalized_names"] = sorted(ja_normalized - us_normalized)
            item["us_only_normalized_names"] = sorted(us_normalized - ja_normalized)
        except (ArchiveError, UnicodeDecodeError, ValueError) as error:
            item["archive_error"] = str(error)
        report.append(item)

    result = {
        "rom_sha256": rom.sha256,
        "paired_resources": len(report),
        "pairs": report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in report:
        ja = item.get("ja_archive")
        if ja:
            print(
                f"{item['ja_path']}: {ja['entry_count']} entries, "
                f"{ja['unique_entry_count']} unique, {ja['suffix_counts']}"
            )
        else:
            print(f"{item['ja_path']}: {item['archive_error']}")
    print(args.output)


if __name__ == "__main__":
    main()
