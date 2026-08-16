#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
if [ "$#" -ne 1 ]; then
  echo "Usage: scripts/check_translation.sh original.nds" >&2
  exit 1
fi
uv run python tools/check_translation.py "$1"
