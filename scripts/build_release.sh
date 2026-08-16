#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
if [ "$#" -ne 1 ]; then
  echo "Usage: scripts/build_release.sh original.nds" >&2
  exit 1
fi
uv run python tools/build_release.py "$1"
