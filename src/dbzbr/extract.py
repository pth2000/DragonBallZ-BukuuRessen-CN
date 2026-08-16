"""Reproducible extraction of all six embedded script languages."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from .archive import PackedArchive
from .nds import NDSRom
from .script import ScriptFile

LANGS = {"jp": "Japanese", "en": "English", "fr": "French", "ge": "German", "it": "Italian", "sp": "Spanish"}


def extract_all(rom_path: str | Path, output_directory: str | Path) -> dict[str, object]:
    rom = NDSRom.from_file(rom_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    archive = PackedArchive(rom.get_file("romdata/scene/script.bin"))
    binary_dir = output / "scripts_decompressed"
    binary_dir.mkdir(exist_ok=True)
    rows: list[dict[str, object]] = []

    for name in archive.names():
        data = archive.unpack(name)
        (binary_dir / name).write_bytes(data)
        _, language, script_ext = name.split("_", 2)
        script_code = script_ext.rsplit(".", 1)[0]
        script = ScriptFile(data)
        script_text_number = 0
        for block in script.blocks:
            block_text_number = 0
            for command in block:
                raw = script.raw_text(command)
                if raw is None:
                    continue
                encoding = "shift_jis" if language == "jp" else "utf-8"
                text = raw.decode(encoding, errors="replace")
                script_text_number += 1
                rows.append(
                    {
                        "language_code": language,
                        "language": LANGS.get(language, language),
                        "script": script_code,
                        "script_file": name,
                        "script_text_no": script_text_number,
                        "block_index": command.block_index,
                        "event_id": f"{command.event_id:08X}",
                        "block_text_no": block_text_number,
                        "command_index": command.command_index,
                        "opcode": f"{command.opcode:02X}",
                        "command_offset": f"{command.offset:08X}",
                        "command_length": command.length,
                        "text_byte_length": len(raw),
                        "line_count": text.count("\\n") + 1,
                        "text": text,
                    }
                )
                block_text_number += 1

    headers = list(rows[0])
    with (output / "multilingual_raw_text.tsv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    plain_root = output / "plain_text"
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["language_code"]), str(row["script"]))].append(row)
    for (language, script_code), group in grouped.items():
        directory = plain_root / language
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{script_code}.txt").open("w", encoding="utf-8") as handle:
            current = None
            for row in group:
                key = (row["block_index"], row["event_id"])
                if key != current:
                    current = key
                    handle.write(f"\n===== BLOCK {key[0]} / EVENT {key[1]} =====\n")
                handle.write(
                    f'[{int(row["script_text_no"]):04d} | CMD {int(row["command_index"]):03d} | OP {row["opcode"]}]\n'
                )
                handle.write(str(row["text"]).replace("\\n", "\n") + "\n\n")

    counts = {language: sum(row["language_code"] == language for row in rows) for language in LANGS}
    report = {
        "game_code": rom.game_code,
        "rom_version": rom.rom_version,
        "rom_sha256": rom.sha256,
        "archive_entries": len(archive.entries),
        "text_records": len(rows),
        "language_counts": counts,
    }
    (output / "extraction_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
