#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
SOURCE="$ROOT/dist/Pyrenees Selects.app"
DESTINATION="/Applications/Pyrenees Selects.app"

if [[ ! -d "$SOURCE" ]]; then
  "$ROOT/scripts/build_macos_app.sh"
fi

rm -rf "$DESTINATION"
ditto "$SOURCE" "$DESTINATION"
codesign --verify --deep --strict "$DESTINATION"
open "$DESTINATION"

print "$DESTINATION"
