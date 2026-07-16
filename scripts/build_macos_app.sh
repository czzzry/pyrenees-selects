#!/bin/zsh
set -euo pipefail

ROOT="${0:A:h:h}"
VENV="$ROOT/.venv-macos"
ICON_SOURCE="$ROOT/packaging/macos/AppIcon.svg"
ICONSET="$ROOT/build/AppIcon.iconset"
ICON="$ROOT/packaging/macos/PyreneesSelects.icns"
APP="$ROOT/dist/Pyrenees Selects.app"
TOOL_CACHE="$ROOT/.cache/macos-tools"
TOOL_DIR="$ROOT/build/media-tools"
FFMPEG_ZIP="$TOOL_CACHE/ffmpeg-8.1.2.zip"
FFPROBE_ZIP="$TOOL_CACHE/ffprobe-8.1.2.zip"
FFMPEG_SHA="e91df72a1ee7c26606f90dd2dd4dcccc6a75140ff9ea6fdd50faae828b82ba69"
FFPROBE_SHA="399b93f0b9862f69767afa343e90c2f48d7e7958cadbb6deb76a012d0e3b7ce3"

if [[ "$(uname -s)" != "Darwin" ]]; then
  print -u2 "The Mac application must be built on macOS."
  exit 1
fi

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$ROOT/requirements-macos.txt"

mkdir -p "$TOOL_CACHE"
if [[ ! -f "$FFMPEG_ZIP" ]]; then
  curl -fL https://evermeet.cx/ffmpeg/ffmpeg-8.1.2.zip -o "$FFMPEG_ZIP"
fi
if [[ ! -f "$FFPROBE_ZIP" ]]; then
  curl -fL https://evermeet.cx/ffmpeg/ffprobe-8.1.2.zip -o "$FFPROBE_ZIP"
fi
[[ "$(shasum -a 256 "$FFMPEG_ZIP" | awk '{print $1}')" == "$FFMPEG_SHA" ]] || { print -u2 "FFmpeg checksum failed."; exit 1; }
[[ "$(shasum -a 256 "$FFPROBE_ZIP" | awk '{print $1}')" == "$FFPROBE_SHA" ]] || { print -u2 "FFprobe checksum failed."; exit 1; }

rm -rf "$ROOT/build" "$ROOT/dist"
mkdir -p "$ICONSET"
mkdir -p "$TOOL_DIR"
unzip -q -o "$FFMPEG_ZIP" -d "$TOOL_DIR"
unzip -q -o "$FFPROBE_ZIP" -d "$TOOL_DIR"
sips -s format png "$ICON_SOURCE" --out "$ROOT/build/AppIcon-1024.png" >/dev/null
for SIZE in 16 32 128 256 512; do
  sips -z "$SIZE" "$SIZE" "$ROOT/build/AppIcon-1024.png" --out "$ICONSET/icon_${SIZE}x${SIZE}.png" >/dev/null
  DOUBLE=$((SIZE * 2))
  sips -z "$DOUBLE" "$DOUBLE" "$ROOT/build/AppIcon-1024.png" --out "$ICONSET/icon_${SIZE}x${SIZE}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICON"

cd "$ROOT"
"$VENV/bin/python" setup_macos.py py2app

codesign --force --sign - "$APP/Contents/Resources/bin/ffmpeg"
codesign --force --sign - "$APP/Contents/Resources/bin/ffprobe"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

print "$APP"
