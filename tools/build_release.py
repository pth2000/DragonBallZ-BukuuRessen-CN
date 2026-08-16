#!/usr/bin/env python3
"""Build the complete translation and its distributable BPS patch."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.bps import apply_patch, create_patch


@dataclass(frozen=True)
class Stage:
    name: str
    script: str
    output_name: str
    font_mode: str = "bdf"


STAGES = (
    Stage("mode", "build_mode_explanations.py", "DBZ_Bukuu_Ressen_CN_AllModeExplanationsTest.nds"),
    Stage("option", "build_option_explanations.py", "DBZ_Bukuu_Ressen_CN_UI_ExplanationsTest.nds"),
    Stage("stage", "build_stage_explanations.py", "DBZ_Bukuu_Ressen_CN_UI_StageTest.nds"),
    Stage("practice", "build_practice_explanations.py", "DBZ_Bukuu_Ressen_CN_UI_PracticeTest.nds"),
    Stage("data", "build_data_ui.py", "DBZ_Bukuu_Ressen_CN_UI_DataTest.nds", "data"),
    Stage("save", "build_save_prompts.py", "DBZ_Bukuu_Ressen_CN_UI_SaveTest.nds"),
    Stage("map_titles", "build_map_titles.py", "DBZ_Bukuu_Ressen_CN_UI_MapTitleTest.nds"),
    Stage("versus", "build_vs_ui.py", "DBZ_Bukuu_Ressen_CN_UI_VSTest.nds"),
    Stage("clear", "build_clear_messages.py", "DBZ_Bukuu_Ressen_CN_UI_ClearTest.nds"),
    Stage("maximum", "build_maximum_explanations.py", "DBZ_Bukuu_Ressen_CN_UI_MaximumTest.nds"),
    Stage(
        "character_status",
        "build_character_status_moves.py",
        "DBZ_Bukuu_Ressen_CN_UI_CharacterStatusTest.nds",
    ),
    Stage(
        "character_data",
        "build_character_data.py",
        "DBZ_Bukuu_Ressen_CN_UI_CharacterDataTest.nds",
    ),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_rmtree(path: Path, allowed_root: Path) -> None:
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise RuntimeError(f"refusing to remove path outside generated stage root: {resolved}")
    if path.exists():
        shutil.rmtree(path)


def run(command: list[str]) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    config = json.loads((PROJECT_ROOT / "project.json").read_text(encoding="utf-8"))
    vendor = PROJECT_ROOT / "work/vendor"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="Exact original ADBJ Rev 0 ROM")
    parser.add_argument("--ark-font-repo", type=Path, default=vendor / "ark-pixel-font")
    parser.add_argument(
        "--fallback-bdf",
        type=Path,
        default=vendor
        / "fusion-pixel-font/12px-monospaced-bdf-v2026.07.20/fusion-pixel-12px-monospaced-zh_hans.bdf",
    )
    parser.add_argument(
        "--menu-label-font",
        type=Path,
        default=vendor / "zhengge-dianhei-16/ZhengGeDianHei-16.ttf",
    )
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "build/release")
    parser.add_argument("--dist-dir", type=Path, default=PROJECT_ROOT / "dist")
    parser.add_argument("--keep-intermediates", action="store_true")
    parser.add_argument(
        "--allow-hash-change",
        action="store_true",
        help="Build even when the result no longer matches the recorded release "
        "hashes, and print the new values. Expected after a translation edit.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove an existing generated output-root before building",
    )
    args = parser.parse_args()

    source = args.rom.read_bytes()
    source_sha256 = sha256_bytes(source)
    if source_sha256 != config["source_sha256"]:
        raise SystemExit(
            "source ROM SHA-256 mismatch\n"
            f"expected: {config['source_sha256']}\nactual:   {source_sha256}"
        )
    for label, path in (
        ("Ark Pixel Font", args.ark_font_repo),
        ("Fusion Pixel Font BDF", args.fallback_bdf),
        ("ZhengGeDianHei 16", args.menu_label_font),
    ):
        if not path.exists():
            raise SystemExit(f"missing {label}: {path}\nrun: uv run python tools/fetch_fonts.py")

    # Normalise before use: a relative --output-root would otherwise reach
    # Path.relative_to(PROJECT_ROOT) at the very end and fail after a full build.
    args.output_root = output_root = args.output_root.resolve()
    args.dist_dir = args.dist_dir.resolve()
    project_build = (PROJECT_ROOT / "build").resolve()
    if output_root != project_build and project_build not in output_root.parents:
        raise SystemExit("--output-root must stay inside the project's build directory")
    if args.output_root.exists() and any(args.output_root.iterdir()):
        if not args.clean:
            raise SystemExit(f"output root is not empty: {args.output_root}; pass --clean")
        if output_root == project_build:
            raise SystemExit("refusing to clean the build directory itself; use a child directory")
        shutil.rmtree(args.output_root)

    stages_root = args.output_root / "stages"
    story_dir = stages_root / "00_story"
    story_rom = story_dir / "story.nds"
    story_patch = story_dir / "story.bps"
    run(
        [
            sys.executable,
            str(PROJECT_ROOT / "tools/build_rom.py"),
            str(args.rom),
            "--ark-font-repo",
            str(args.ark_font_repo),
            "--fallback-bdf",
            str(args.fallback_bdf),
            "--output",
            str(story_rom),
            "--patch",
            str(story_patch),
        ]
    )

    previous_dir = story_dir
    previous_rom = story_rom
    for index, stage in enumerate(STAGES, start=1):
        stage_dir = stages_root / f"{index:02d}_{stage.name}"
        command = [
            sys.executable,
            str(PROJECT_ROOT / "tools" / stage.script),
            "--base-rom",
            str(previous_rom),
            "--source-rom",
            str(args.rom),
            "--output-dir",
            str(stage_dir),
        ]
        if stage.font_mode == "data":
            command.extend(
                [
                    "--help-bdf",
                    str(args.fallback_bdf),
                    "--menu-bdf",
                    str(args.fallback_bdf),
                    "--menu-label-font",
                    str(args.menu_label_font),
                ]
            )
        else:
            command.extend(["--bdf", str(args.fallback_bdf)])
        run(command)
        stage_rom = stage_dir / stage.output_name
        if not stage_rom.is_file():
            raise RuntimeError(f"stage did not produce expected ROM: {stage_rom}")
        if not args.keep_intermediates:
            safe_rmtree(previous_dir, stages_root)
        previous_dir = stage_dir
        previous_rom = stage_rom

    final_bytes = previous_rom.read_bytes()
    target_sha256 = sha256_bytes(final_bytes)
    target_changed = target_sha256 != config["release_target_sha256"]
    if target_changed and not args.allow_hash_change:
        raise RuntimeError(
            "release target SHA-256 mismatch\n"
            f"expected: {config['release_target_sha256']}\nactual:   {target_sha256}\n"
            "\nAny translation or resource edit changes this hash. To build anyway "
            "and report the new values, re-run with --allow-hash-change."
        )

    args.output_root.mkdir(parents=True, exist_ok=True)
    final_rom = args.output_root / "DBZ_Bukuu_Ressen_CN.nds"
    final_rom.write_bytes(final_bytes)

    patch_name = config["release_patch_name"]
    args.dist_dir.mkdir(parents=True, exist_ok=True)
    patch_path = args.dist_dir / patch_name
    patch = create_patch(source, final_bytes, metadata=b"DBZ Bukuu Ressen CN")
    if apply_patch(source, patch) != final_bytes:
        raise RuntimeError("release BPS failed round-trip validation")
    patch_path.write_bytes(patch)
    patch_sha256 = sha256_bytes(patch)
    patch_changed = patch_sha256 != config["release_patch_sha256"]
    if patch_changed and not args.allow_hash_change:
        raise RuntimeError(
            "release patch SHA-256 mismatch\n"
            f"expected: {config['release_patch_sha256']}\nactual:   {patch_sha256}"
        )

    manifest = {
        "game_code": config["game_code"],
        "source_rom_size": len(source),
        "source_rom_sha256": source_sha256,
        "target_rom_size": len(final_bytes),
        "target_rom_sha256": target_sha256,
        "local_target_rom": final_rom.relative_to(PROJECT_ROOT).as_posix(),
        "patch_file": patch_name,
        "patch_size": len(patch),
        "patch_sha256": patch_sha256,
    }
    (args.dist_dir / "release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.dist_dir / "SHA256SUMS.txt").write_text(
        f"{patch_sha256}  {patch_name}\n", encoding="ascii"
    )

    if not args.keep_intermediates:
        safe_rmtree(previous_dir, stages_root)
        if stages_root.exists() and not any(stages_root.iterdir()):
            stages_root.rmdir()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if target_changed or patch_changed:
        print(
            "\nThis build no longer matches the recorded release hashes.\n"
            "Report these in the pull request; a maintainer updates project.json:\n"
            f"  release_target_sha256  {target_sha256}\n"
            f"  release_patch_sha256   {patch_sha256}"
        )


if __name__ == "__main__":
    main()
