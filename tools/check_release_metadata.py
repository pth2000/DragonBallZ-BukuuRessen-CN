#!/usr/bin/env python3
"""Check that hashes quoted in the documentation are current.

Hashes get copied into prose and then go stale when the build changes. This
finds every 64-hex string in the tracked documentation and requires it to match
a value the project actually uses: the ROM and patch hashes in `project.json`,
or the third-party font checksums that `fetch_fonts.py` verifies.

It deliberately does not require any document to mention a hash: what each page
covers is an editorial choice, and a page that quotes nothing cannot drift.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys

from _bootstrap import PROJECT_ROOT

HASH = re.compile(r"\b[0-9a-f]{64}\b")
SKIP_DIRECTORIES = {".git", ".venv", "build", "dist", "work", "__pycache__", ".ruff_cache"}
# Hash-valued keys in project.json, plus the bundled font baseline.
HASH_KEYS = ("source_sha256", "baseline_target_sha256", "release_target_sha256", "release_patch_sha256")


def font_hashes() -> dict[str, str]:
    """Third-party font checksums, read from the fetcher that enforces them."""
    source = (PROJECT_ROOT / "tools/fetch_fonts.py").read_text(encoding="utf-8")
    return {
        value: name
        for name, value in re.findall(r'(\w*SHA256)\s*=\s*"([0-9a-f]{64})"', source)
    }


def main() -> None:
    config = json.loads((PROJECT_ROOT / "project.json").read_text(encoding="utf-8"))
    known = {config[key]: key for key in HASH_KEYS if key in config}
    known.update(font_hashes())
    problems: list[str] = []

    for path in sorted(PROJECT_ROOT.rglob("*.md")):
        relative = path.relative_to(PROJECT_ROOT)
        if set(relative.parts) & SKIP_DIRECTORIES:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for value in HASH.findall(line):
                if value not in known:
                    problems.append(
                        f"{relative.as_posix()}:{number}: {value} 不是当前使用的任何哈希"
                    )

    patch = PROJECT_ROOT / "dist" / config["release_patch_name"]
    if patch.is_file():
        actual = hashlib.sha256(patch.read_bytes()).hexdigest()
        if actual != config["release_patch_sha256"]:
            problems.append(
                f"dist/{config['release_patch_name']}: 实际哈希 {actual} 与 project.json 不一致"
            )

    if problems:
        print("发布元数据检查未通过:")
        for problem in problems:
            print(f"- {problem}")
        sys.exit(1)

    quoted = {
        known[value]
        for path in PROJECT_ROOT.rglob("*.md")
        if not set(path.relative_to(PROJECT_ROOT).parts) & SKIP_DIRECTORIES
        for value in HASH.findall(path.read_text(encoding="utf-8"))
    }
    print(f"发布元数据一致（文档引用 {len(quoted)} 类哈希，均为当前值）")


if __name__ == "__main__":
    main()
