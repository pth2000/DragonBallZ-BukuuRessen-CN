#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PROJECT_ROOT  # noqa: F401

from dbzbr.bps import apply_patch


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a BPS patch.")
    parser.add_argument("source", type=Path)
    parser.add_argument("patch", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_bytes(apply_patch(args.source.read_bytes(), args.patch.read_bytes()))
    print(args.output)


if __name__ == "__main__":
    main()
