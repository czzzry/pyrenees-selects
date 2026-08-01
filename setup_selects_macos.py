from __future__ import annotations

import os
from pathlib import Path

from setuptools import setup


ROOT = Path(__file__).parent.resolve()
FFMPEG = Path(os.environ.get("SELECTS_BUILD_FFMPEG", ROOT / "build" / "selects-media-tools" / "ffmpeg")).resolve()
FFPROBE = Path(os.environ.get("SELECTS_BUILD_FFPROBE", ROOT / "build" / "selects-media-tools" / "ffprobe")).resolve()
ICON = ROOT / "packaging" / "macos" / "PyreneesSelects.icns"

for required in (FFMPEG, FFPROBE, ICON):
    if not required.is_file():
        raise FileNotFoundError(f"Required Mac application resource not found: {required}")

def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


static_files = sorted((ROOT / "pyrenees_selects" / "static").iterdir())

setup(
    name="Selects",
    version="0.7.0",
    app=["selects_macos_launcher.py"],
    packages=["pyrenees_selects"],
    data_files=[
        ("static", [relative(path) for path in static_files]),
        ("bin", [relative(FFMPEG), relative(FFPROBE)]),
        ("licenses", ["LICENSE", "packaging/macos/FFMPEG-NOTICE.txt"]),
    ],
    options={
        "py2app": {
            "argv_emulation": False,
            "arch": "x86_64",
            "iconfile": str(ICON),
            "packages": ["webview"],
            "includes": ["webview.platforms.cocoa"],
            "excludes": [
                "setuptools", "test", "tkinter", "unittest", "webview.platforms.android",
                "webview.platforms.cef", "webview.platforms.edgechromium", "webview.platforms.gtk",
                "webview.platforms.mshtml", "webview.platforms.qt", "webview.platforms.win32",
                "webview.platforms.winforms",
            ],
            "plist": {
                "CFBundleDisplayName": "Selects",
                "CFBundleIdentifier": "com.cezarybaraniecki.selects",
                "CFBundleName": "Selects",
                "CFBundleShortVersionString": "0.7.0",
                "CFBundleVersion": "1",
                "LSApplicationCategoryType": "public.app-category.video",
                "LSMinimumSystemVersion": "12.0",
                "NSHighResolutionCapable": True,
                "NSDocumentsFolderUsageDescription": "Selects reads only footage folders you choose and never modifies the originals.",
                "NSRemovableVolumesUsageDescription": "Selects can read footage from a removable drive that you choose.",
                "NSHumanReadableCopyright": "Copyright © 2026 Selects contributors",
            },
        }
    },
)
