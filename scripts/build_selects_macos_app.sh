#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
VENV="$ROOT/.venv-selects-macos"
TOOL_CACHE="$ROOT/.cache/macos-tools"
TOOL_DIR="$ROOT/build/selects-media-tools"
BUILD_DIR="$ROOT/build/selects-py2app"
DIST_DIR="$ROOT/dist/selects"
APP="$DIST_DIR/Selects.app"
ARCHIVE="$ROOT/dist/Selects-0.7.0-macos-x86_64.zip"
FFMPEG_ZIP="$TOOL_CACHE/ffmpeg-8.1.2.zip"
FFPROBE_ZIP="$TOOL_CACHE/ffprobe-8.1.2.zip"
FFMPEG_SHA="e91df72a1ee7c26606f90dd2dd4dcccc6a75140ff9ea6fdd50faae828b82ba69"
FFPROBE_SHA="399b93f0b9862f69767afa343e90c2f48d7e7958cadbb6deb76a012d0e3b7ce3"
SIGN_IDENTITY="${SELECTS_SIGN_IDENTITY:--}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  print -u2 "Selects.app must be built on macOS."
  exit 1
fi

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$ROOT/requirements-macos.txt"

mkdir -p "$TOOL_CACHE" "$TOOL_DIR" "$DIST_DIR"
[[ -f "$FFMPEG_ZIP" ]] || curl -fL https://evermeet.cx/ffmpeg/ffmpeg-8.1.2.zip -o "$FFMPEG_ZIP"
[[ -f "$FFPROBE_ZIP" ]] || curl -fL https://evermeet.cx/ffmpeg/ffprobe-8.1.2.zip -o "$FFPROBE_ZIP"
[[ "$(shasum -a 256 "$FFMPEG_ZIP" | awk '{print $1}')" == "$FFMPEG_SHA" ]] || { print -u2 "FFmpeg checksum failed."; exit 1; }
[[ "$(shasum -a 256 "$FFPROBE_ZIP" | awk '{print $1}')" == "$FFPROBE_SHA" ]] || { print -u2 "FFprobe checksum failed."; exit 1; }
unzip -q -o "$FFMPEG_ZIP" -d "$TOOL_DIR"
unzip -q -o "$FFPROBE_ZIP" -d "$TOOL_DIR"

"$VENV/bin/python" - "$BUILD_DIR" "$APP" "$ARCHIVE" "$ROOT/selects_preeditor.egg-info" <<'PY'
import shutil, sys
from pathlib import Path
for raw in sys.argv[1:]:
    path = Path(raw)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
PY

cd "$ROOT"
"$VENV/bin/python" setup_selects_macos.py py2app --bdist-base "$BUILD_DIR" --dist-dir "$DIST_DIR"

if [[ "$SIGN_IDENTITY" == "-" ]]; then
  codesign --force --sign - "$APP/Contents/Resources/bin/ffmpeg"
  codesign --force --sign - "$APP/Contents/Resources/bin/ffprobe"
  codesign --force --deep --sign - "$APP"
else
  codesign --force --options runtime --timestamp --sign "$SIGN_IDENTITY" "$APP/Contents/Resources/bin/ffmpeg"
  codesign --force --options runtime --timestamp --sign "$SIGN_IDENTITY" "$APP/Contents/Resources/bin/ffprobe"
  codesign --force --deep --options runtime --timestamp --sign "$SIGN_IDENTITY" "$APP"
fi
codesign --verify --deep --strict "$APP"
spctl --assess --type execute "$APP" || [[ "$SIGN_IDENTITY" == "-" ]]

ditto -c -k --sequesterRsrc --keepParent "$APP" "$ARCHIVE"
print "$APP"
print "$ARCHIVE"
