#!/usr/bin/env python3
"""Re-run interface stages against a recorded baseline and compare hashes.

Refactoring the stage builders must not change a single byte of their output.
This runs each stage on top of the matching baseline ROM and checks the result
against the hashes captured from the last known-good full build.

    uv run python tools/build_release.py <rom> --output-root build/baseline \
        --dist-dir build/baseline/dist --keep-intermediates
    uv run python tools/verify_stages.py --record
    uv run python tools/verify_stages.py maximum character_data
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from _bootstrap import PROJECT_ROOT

# stage name -> (builder, baseline directory, produced ROM name)
STAGES: dict[str, tuple[str, str, str]] = {
    "mode": ("build_mode_explanations.py", "01_mode", "DBZ_Bukuu_Ressen_CN_AllModeExplanationsTest.nds"),
    "option": ("build_option_explanations.py", "02_option", "DBZ_Bukuu_Ressen_CN_UI_ExplanationsTest.nds"),
    "stage": ("build_stage_explanations.py", "03_stage", "DBZ_Bukuu_Ressen_CN_UI_StageTest.nds"),
    "practice": ("build_practice_explanations.py", "04_practice", "DBZ_Bukuu_Ressen_CN_UI_PracticeTest.nds"),
    "data": ("build_data_ui.py", "05_data", "DBZ_Bukuu_Ressen_CN_UI_DataTest.nds"),
    "save": ("build_save_prompts.py", "06_save", "DBZ_Bukuu_Ressen_CN_UI_SaveTest.nds"),
    "map_titles": ("build_map_titles.py", "07_map_titles", "DBZ_Bukuu_Ressen_CN_UI_MapTitleTest.nds"),
    "versus": ("build_vs_ui.py", "08_versus", "DBZ_Bukuu_Ressen_CN_UI_VSTest.nds"),
    "clear": ("build_clear_messages.py", "09_clear", "DBZ_Bukuu_Ressen_CN_UI_ClearTest.nds"),
    "maximum": ("build_maximum_explanations.py", "10_maximum", "DBZ_Bukuu_Ressen_CN_UI_MaximumTest.nds"),
    "character_status": (
        "build_character_status_moves.py",
        "11_character_status",
        "DBZ_Bukuu_Ressen_CN_UI_CharacterStatusTest.nds",
    ),
    "character_data": (
        "build_character_data.py",
        "12_character_data",
        "DBZ_Bukuu_Ressen_CN_UI_CharacterDataTest.nds",
    ),
}
ORDER = list(STAGES)
VENDOR = PROJECT_ROOT / "work/vendor"
FUSION = VENDOR / "fusion-pixel-font/12px-monospaced-bdf-v2026.07.20/fusion-pixel-12px-monospaced-zh_hans.bdf"


def previous_rom(stage: str, baseline: Path) -> Path:
    index = ORDER.index(stage)
    if index == 0:
        return baseline / "stages/00_story/story.nds"
    previous = ORDER[index - 1]
    _, directory, rom_name = STAGES[previous]
    return baseline / "stages" / directory / rom_name


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(baseline: Path, output: Path) -> None:
    hashes = {}
    for directory in sorted((baseline / "stages").iterdir()):
        roms = sorted(directory.glob("*.nds"))
        if roms:
            hashes[directory.name] = sha256(roms[0])
    output.write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    print(f"recorded {len(hashes)} stage hashes -> {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stages", nargs="*", choices=[*ORDER, []], help="stages to verify; default all")
    parser.add_argument("--baseline", type=Path, default=PROJECT_ROOT / "build/baseline")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "build/verify")
    parser.add_argument("--record", action="store_true", help="record hashes from the baseline instead")
    args = parser.parse_args()

    hash_file = args.baseline / "stage_hashes.json"
    if args.record:
        record(args.baseline, hash_file)
        return

    if not hash_file.is_file():
        raise SystemExit(f"missing baseline hashes: {hash_file}\nrun with --record first")
    expected = json.loads(hash_file.read_text(encoding="utf-8"))

    failures = []
    for stage in args.stages or ORDER:
        script, directory, rom_name = STAGES[stage]
        base = previous_rom(stage, args.baseline)
        if not base.is_file():
            print(f"{stage:<18} SKIP  missing base ROM {base}")
            continue
        target = args.output_dir / directory
        command = [
            sys.executable,
            str(PROJECT_ROOT / "tools" / script),
            "--base-rom", str(base),
            "--source-rom", str(PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds"),
            "--output-dir", str(target),
        ]
        if stage == "data":
            command += [
                "--help-bdf", str(FUSION),
                "--menu-bdf", str(FUSION),
                "--menu-label-font", str(VENDOR / "zhengge-dianhei-16/ZhengGeDianHei-16.ttf"),
            ]
        else:
            command += ["--bdf", str(FUSION)]

        # Builders print Chinese; force UTF-8 rather than the Windows ANSI default.
        done = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if done.returncode:
            print(f"{stage:<18} ERROR build failed")
            print(done.stderr.strip()[-800:])
            failures.append(stage)
            continue
        produced = target / rom_name
        actual = sha256(produced)
        if actual != expected.get(directory):
            print(f"{stage:<18} DIFF  {actual[:16]} != {str(expected.get(directory))[:16]}")
            failures.append(stage)
            continue

        # The ROM hash misses previews and reports, which is exactly where a
        # refactor can drift unnoticed. Compare every other artefact too.
        baseline_dir = args.baseline / "stages" / directory
        drifted = []
        for path in sorted(baseline_dir.iterdir()):
            if not path.is_file() or path.suffix in {".nds", ".bps"}:
                continue
            mirror = target / path.name
            if not mirror.is_file():
                drifted.append(f"{path.name} missing")
            elif path.suffix != ".json" and sha256(mirror) != sha256(path):
                drifted.append(path.name)
        if drifted:
            print(f"{stage:<18} DIFF  ROM matches but artefacts differ: {', '.join(drifted)}")
            failures.append(stage)
        else:
            print(f"{stage:<18} OK    {actual[:16]}")

    if failures:
        raise SystemExit(f"\n{len(failures)} stage(s) differ from the baseline: {', '.join(failures)}")
    print("\nall verified stages match the baseline")


if __name__ == "__main__":
    main()
