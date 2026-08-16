#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.archive import PackedArchive
from dbzbr.build import TextEncoder, iter_text_characters, load_existing_assignments, read_tsv
from dbzbr.font import find_font_map
from dbzbr.nds import NDSRom
from dbzbr.script import TEXT_START, ScriptFile


def main() -> None:
    parser = argparse.ArgumentParser(description="Check glyph coverage and fixed command byte budgets.")
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--translation",
        type=Path,
        default=PROJECT_ROOT / "data/translation/story_zh.tsv",
    )
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "build/translation_check.tsv")
    args = parser.parse_args()

    config = json.loads((PROJECT_ROOT / "project.json").read_text(encoding="utf-8"))
    rom = NDSRom.from_file(args.rom)
    _, entries = find_font_map(rom.arm9())
    entries_by_code = {entry.code: entry for entry in entries}
    assignments = load_existing_assignments(PROJECT_ROOT / config["custom_glyph_map"], entries_by_code)
    encoder = TextEncoder(entries_by_code, assignments)
    archive = PackedArchive(rom.get_file(config["script_path"]))
    scripts: dict[str, ScriptFile] = {}
    results = []
    missing = set()

    for row in read_tsv(args.translation):
        text = row.get("简体中文", "")
        if not text:
            continue
        script_code = row["脚本"]
        if script_code not in scripts:
            scripts[script_code] = ScriptFile(archive.unpack(f"script_jp_{script_code}.bin"))
        command = scripts[script_code].command(int(row["剧情块"]), int(row["指令序号"]))
        capacity = command.length - 2 - TEXT_START[command.opcode]
        try:
            encoded = encoder.encode(text)
            used = len(encoded)
            glyph_status = "ok"
        except Exception:
            used = -1
            glyph_status = "missing"
            for character in iter_text_characters(text):
                if character != "\\n" and encoder.code_for(character) is None:
                    missing.add(character)
        results.append(
            {
                "ID": row.get("ID", ""),
                "脚本": script_code,
                "剧情块": row["剧情块"],
                "指令序号": row["指令序号"],
                "容量字节": capacity,
                "使用字节": used,
                "剩余字节": capacity - used if used >= 0 else "",
                "字形状态": glyph_status,
                "长度状态": "超长" if used > capacity else ("未知" if used < 0 else "正常"),
                # The public translation table carries no Japanese; reading it
                # from the caller's own ROM gives proofreaders the original to
                # compare against without shipping it in the repository.
                "日文原文": scripts[script_code].decode_text(command) or "",
                "简体中文": text,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    headers = list(results[0]) if results else ["ID"]
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    print(f"translated rows: {len(results)}")
    print(f"over budget: {sum(row['长度状态'] == '超长' for row in results)}")
    print("missing glyphs:", "".join(sorted(missing)) or "none")
    print(args.output)


if __name__ == "__main__":
    main()
