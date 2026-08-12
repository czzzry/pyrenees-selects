#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
SOURCE="$ROOT/packaging/macos/AppIcon.svg"
DESTINATION="${1:-$ROOT/build/Selects.icns}"
WORK_DIR="$ROOT/build/Selects.iconset"
BASE="$ROOT/build/Selects-icon-1024.png"

if [[ "$(uname -s)" != "Darwin" ]]; then
  print -u2 "Selects icons must be generated on macOS."
  exit 1
fi

mkdir -p "$ROOT/build" "${DESTINATION:h}"
sips -s format png "$SOURCE" --out "$BASE" >/dev/null
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$BASE" --out "$WORK_DIR/icon_${size}x${size}.png" >/dev/null
  doubled=$((size * 2))
  sips -z "$doubled" "$doubled" "$BASE" --out "$WORK_DIR/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns "$WORK_DIR" -o "$DESTINATION"
print "$DESTINATION"
