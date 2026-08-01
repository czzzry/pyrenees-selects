#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if ! command -v python3 >/dev/null 2>&1; then
  echo "Selects needs Python 3.11 or later. Install Python, then run this again." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "Selects needs ffmpeg and ffprobe." >&2
  echo "On macOS with Homebrew: brew install ffmpeg" >&2
  exit 1
fi

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else "Selects needs Python 3.11 or later.")'
python3 -m venv "$PROJECT_DIR/.venv-selects"
"$PROJECT_DIR/.venv-selects/bin/python" -m pip install --quiet --upgrade pip
"$PROJECT_DIR/.venv-selects/bin/python" -m pip install --quiet "$PROJECT_DIR"
"$PROJECT_DIR/.venv-selects/bin/selects" doctor

echo "Selects is installed. Run ./scripts/run_selects.sh"
