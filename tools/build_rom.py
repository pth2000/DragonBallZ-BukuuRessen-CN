#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.build import BuildOptions, build_project


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a translated NDS ROM and BPS patch.")
    parser.add_argument("rom", type=Path, help="Exact original ADBJ ROM")
    parser.add_argument(
        "--translation",
        type=Path,
        default=PROJECT_ROOT / "data/translation/story_zh.tsv",
        help="Translation TSV",
    )
    parser.add_argument("--ark-font-repo", type=Path, help="Local clone/extract of TakWolf/ark-pixel-font")
    parser.add_argument("--ark-size", type=int, default=12, choices=(10, 12, 16))
    parser.add_argument(
        "--fallback-bdf",
        type=Path,
        help="Optional BDF used only when Ark lacks a required glyph",
    )
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "build/DBZ_Bukuu_Ressen_CN.nds")
    parser.add_argument("--patch", type=Path, default=PROJECT_ROOT / "build/DBZ_Bukuu_Ressen_CN.bps")
    parser.add_argument("--update-map", action="store_true", help="Persist newly allocated glyph mappings")
    args = parser.parse_args()

    result = build_project(
        BuildOptions(
            project_root=PROJECT_ROOT,
            source_rom=args.rom,
            output_rom=args.output,
            output_patch=args.patch,
            translation_table=args.translation,
            ark_font_root=args.ark_font_repo,
            ark_size=args.ark_size,
            fallback_bdf=args.fallback_bdf,
            update_map=args.update_map,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
