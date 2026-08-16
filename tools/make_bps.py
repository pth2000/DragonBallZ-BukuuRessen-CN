#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PROJECT_ROOT  # noqa: F401

from dbzbr.bps import create_patch


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a deterministic BPS patch.")
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--metadata", default="DBZ Bukuu Ressen CN project")
    args = parser.parse_args()
    args.output.write_bytes(create_patch(args.source.read_bytes(), args.target.read_bytes(), args.metadata.encode()))
    print(args.output)


if __name__ == "__main__":
    main()
