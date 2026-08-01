#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SELECTS_BIN="$PROJECT_DIR/.venv-selects/bin/selects"

if [ ! -x "$SELECTS_BIN" ]; then
  echo "Run ./scripts/bootstrap_selects.sh first." >&2
  exit 1
fi

exec "$SELECTS_BIN" serve "$@"
