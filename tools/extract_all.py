#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.extract import extract_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract all 96 embedded story scripts.")
    parser.add_argument("rom", type=Path)
    parser.add_argument("output", type=Path, nargs="?", default=PROJECT_ROOT / "work/extracted")
    args = parser.parse_args()
    print(json.dumps(extract_all(args.rom, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
