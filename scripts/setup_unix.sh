#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi
uv sync --frozen
echo "Environment ready. Run: uv run python tools/fetch_fonts.py"
