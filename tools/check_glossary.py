#!/usr/bin/env python3
"""Check the glossary against the translation tables.

Verify that each source term has one Chinese rendering and that every glossary
entry remains present in the translation data from which it was derived.
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

from _bootstrap import PROJECT_ROOT

TRANSLATION_DIR = PROJECT_ROOT / "data/translation"

# Source terms whose Chinese rendering is allowed to differ from the character
# entry they contain. Empty: every embedded character name currently matches.
KNOWN_DRIFT: set[tuple[str, str]] = set()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def translation_corpus() -> str:
    """Every Chinese string the project writes into the ROM, concatenated."""
    chunks: list[str] = []
    for path in sorted(TRANSLATION_DIR.glob("*.tsv")):
        for row in read_tsv(path):
            chunks.extend(value for key, value in row.items() if key and "chinese" in key.lower())
            chunks.append(row.get("简体中文", ""))
    return "\n".join(chunk for chunk in chunks if chunk)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--glossary", type=Path, default=PROJECT_ROOT / "data/glossary/terms.tsv"
    )
    args = parser.parse_args()

    rows = read_tsv(args.glossary)
    problems: list[str] = []

    by_japanese: dict[str, set[str]] = collections.defaultdict(set)
    by_chinese: dict[str, set[str]] = collections.defaultdict(set)
    for row in rows:
        by_japanese[row["japanese"]].add(row["simplified_chinese"])
        by_chinese[row["simplified_chinese"]].add(row["japanese"])

    for japanese, chinese in sorted(by_japanese.items()):
        if len(chinese) > 1:
            problems.append(
                f"源词 {japanese} 对应多个译名: {' / '.join(sorted(chinese))}"
            )

    corpus = translation_corpus()
    missing = [row for row in rows if row["simplified_chinese"] not in corpus]
    for row in missing:
        problems.append(
            f"译名 {row['simplified_chinese']}（{row['japanese']}）未出现在任何翻译表中"
        )

    # A character name embedded in a move name should keep the same rendering,
    # otherwise the same person appears under two names.
    people = [row for row in rows if row["category"] == "角色"]
    known: list[str] = []
    for person in people:
        for row in rows:
            if row["category"] == "角色" or person["japanese"] == row["japanese"]:
                continue
            if person["japanese"] not in row["japanese"]:
                continue
            if person["simplified_chinese"] in row["simplified_chinese"]:
                continue
            message = (
                f"{person['japanese']} 译作 {person['simplified_chinese']}，"
                f"但 {row['japanese']} 译作 {row['simplified_chinese']}"
            )
            if (person["japanese"], row["japanese"]) in KNOWN_DRIFT:
                known.append(message)
            else:
                problems.append(message)

    merged = {zh: jp for zh, jp in by_chinese.items() if len(jp) > 1}

    print(f"术语 {len(rows)} 条")
    print(f"  角色 {sum(1 for r in rows if r['category'] == '角色')}")
    print(f"  招式 {sum(1 for r in rows if r['category'] == '招式')}")
    print(f"  特殊能力 {sum(1 for r in rows if r['category'] == '特殊能力')}")
    print(f"  团队必杀技 {sum(1 for r in rows if r['category'] == '团队必杀技')}")

    if merged:
        # Not an error: the original Japanese is inconsistent in places and the
        # translation deliberately unifies it.
        print(f"\n统一了 {len(merged)} 组原文拼写差异:")
        for chinese, japanese in sorted(merged.items()):
            print(f"  {chinese}  <-  {' / '.join(sorted(japanese))}")

    if known:
        print(f"\n已登记的待修正译名（{len(known)}）:")
        for message in known:
            print(f"  {message}")

    if problems:
        print("\n术语检查未通过:")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print("\n术语检查通过")


if __name__ == "__main__":
    main()
