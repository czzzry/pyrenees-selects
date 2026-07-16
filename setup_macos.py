from __future__ import annotations

import os
from pathlib import Path

from setuptools import setup


ROOT = Path(__file__).parent.resolve()
FFMPEG = Path(os.environ.get("PYRENEES_SELECTS_BUILD_FFMPEG", ROOT / "build" / "media-tools" / "ffmpeg")).resolve()
FFPROBE = Path(os.environ.get("PYRENEES_SELECTS_BUILD_FFPROBE", ROOT / "build" / "media-tools" / "ffprobe")).resolve()
ICON = ROOT / "packaging" / "macos" / "PyreneesSelects.icns"

for required in (FFMPEG, FFPROBE, ICON):
    if not required.is_file():
        raise FileNotFoundError(f"Required Mac application resource not found: {required}")

static_files = sorted((ROOT / "pyrenees_selects" / "static").iterdir())

setup(
    name="Pyrenees Selects",
    version="0.2.0",
    app=[str(ROOT / "macos_launcher.py")],
    packages=["pyrenees_selects"],
    data_files=[
        ("static", [str(path) for path in static_files]),
        ("bin", [str(FFMPEG), str(FFPROBE)]),
        ("licenses", [str(ROOT / "LICENSE"), str(ROOT / "packaging" / "macos" / "FFMPEG-NOTICE.txt")]),
    ],
    options={
        "py2app": {
            "argv_emulation": False,
            "arch": "x86_64",
            "iconfile": str(ICON),
            "packages": ["webview"],
            "includes": ["webview.platforms.cocoa"],
            "excludes": [
                "setuptools",
                "test",
                "tkinter",
                "unittest",
                "webview.platforms.android",
                "webview.platforms.cef",
                "webview.platforms.edgechromium",
                "webview.platforms.gtk",
                "webview.platforms.mshtml",
                "webview.platforms.qt",
                "webview.platforms.win32",
                "webview.platforms.winforms",
            ],
            "plist": {
                "CFBundleDisplayName": "Pyrenees Selects",
                "CFBundleIdentifier": "com.cezarybaraniecki.pyreneesselects",
                "CFBundleName": "Pyrenees Selects",
                "CFBundleShortVersionString": "0.2.0",
                "CFBundleVersion": "2",
                "LSApplicationCategoryType": "public.app-category.video",
                "LSMinimumSystemVersion": "12.0",
                "NSHighResolutionCapable": True,
                "NSDocumentsFolderUsageDescription": "Pyrenees Selects reads only the footage library you choose and stores review media separately.",
                "NSHumanReadableCopyright": "Copyright © 2026 Cezary Baraniecki",
                "NSRequiresAquaSystemAppearance": False,
            },
        }
    },
)
