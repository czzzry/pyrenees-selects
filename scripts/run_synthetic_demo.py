#!/usr/bin/env python3
"""Generate a tiny test-pattern library and launch a private local demo."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyrenees_selects.server import build_application, run


DEMO_CLIPS = (
    ("01-coastline-synthetic.mp4", "0", "2024-06-09T08:00:00Z"),
    ("02-foothills-synthetic.mp4", "65", "2024-06-24T10:30:00Z"),
    ("03-high-country-synthetic.mp4", "135", "2024-07-08T15:45:00Z"),
    ("04-journeys-end-synthetic.mp4", "220", "2024-07-19T18:15:00Z"),
)


def build_clip_command(
    ffmpeg: str,
    destination: Path,
    hue: str,
    captured_at: str,
) -> list[str]:
    return [
        ffmpeg,
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x360:rate=24",
        "-t",
        "10",
        "-an",
        "-vf",
        f"hue=h={hue}",
        "-metadata",
        f"creation_time={captured_at}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-y",
        str(destination),
    ]


def create_demo_library(library_dir: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for the synthetic demo. On macOS: brew install ffmpeg")
    library_dir.mkdir(parents=True, exist_ok=True)
    for filename, hue, captured_at in DEMO_CLIPS:
        destination = library_dir / filename
        if destination.is_file() and destination.stat().st_size > 0:
            continue
        subprocess.run(
            build_clip_command(ffmpeg, destination, hue, captured_at),
            check=True,
            timeout=90,
        )


def prepare_demo(library_dir: Path, data_dir: Path) -> None:
    create_demo_library(library_dir)
    application = build_application(data_dir, str(library_dir))
    project = application.create_project("Synthetic journey demo", str(library_dir))
    application.scan(project["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pyrenees Selects with generated test-pattern footage.")
    parser.add_argument("--library-dir", type=Path, default=ROOT / ".demo" / "footage")
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".demo" / "app-data")
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    library_dir = args.library_dir.expanduser().resolve()
    data_dir = args.data_dir.expanduser().resolve()
    prepare_demo(library_dir, data_dir)
    print("Synthetic test-pattern footage is ready. No personal media is used.")
    run(
        "127.0.0.1",
        args.port,
        data_dir=data_dir,
        default_source=str(library_dir),
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
