#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from dbzbr.bps import apply_patch


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the bundled technical font baseline patch.")
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "work/DBZ_Bukuu_Ressen_CN_baseline.nds")
    args = parser.parse_args()
    config = json.loads((PROJECT_ROOT / "project.json").read_text(encoding="utf-8"))
    source = args.rom.read_bytes()
    if hashlib.sha256(source).hexdigest() != config["source_sha256"]:
        raise SystemExit("source ROM SHA-256 mismatch")
    target = apply_patch(source, (PROJECT_ROOT / config["baseline_patch"]).read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target)
    print(args.output)
    print(hashlib.sha256(target).hexdigest())


if __name__ == "__main__":
    main()
