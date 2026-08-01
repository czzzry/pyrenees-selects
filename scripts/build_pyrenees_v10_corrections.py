#!/usr/bin/env python3
"""Build the clean v10 opener and correctly oriented C129 preview master."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path("/Users/cezarybaraniecki/Library/Application Support/Pyrenees Selects")
V5 = ROOT / "revisions_v5"
V8 = ROOT / "revisions_v8"
V10 = ROOT / "revisions_v10"
PHONE = Path(
    "/Users/cezarybaraniecki/Documents/AI project/AI Video Editor/"
    "raw_footage/phone_pyrenees_2024"
)
FPS = "30000/1001"
VIDEO = (
    "-c:v",
    "h264_videotoolbox",
    "-b:v",
    "45000k",
    "-maxrate",
    "60000k",
    "-bufsize",
    "90000k",
    "-movflags",
    "+faststart",
)


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def build_clean_opening() -> None:
    title = V5 / "Pyrenees-Mountain-Lake-Extended-Cut-Title-v5.mov"
    current = V8 / "Pyrenees-approved-opening-v8-exact.mp4"
    destination = V10 / "Pyrenees-clean-opening-no-beach-v10.mp4"
    run(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(title),
        "-ss",
        "4.004",
        "-t",
        "2.002",
        "-i",
        str(current),
        "-filter_complex",
        (
            f"[0:v]trim=start=0:end=3.25,"
            "setpts=(PTS-STARTPTS)*1.230769231,"
            f"fps={FPS},scale=3840:2160:flags=lanczos,setsar=1[title];"
            f"[1:v]setpts=PTS-STARTPTS,fps={FPS},"
            "scale=3840:2160:flags=lanczos,setsar=1[train];"
            "[title][train]concat=n=2:v=1:a=0,"
            "trim=end_frame=180,setpts=PTS-STARTPTS,format=nv12[out]"
        ),
        "-map",
        "[out]",
        "-frames:v",
        "180",
        "-an",
        *VIDEO,
        str(destination),
    )


def build_horizontal_c129() -> None:
    source = PHONE / "PXL_20240617_072941884.mp4"
    destination = V10 / "C129-continuation-05to13-horizontal-v10.mp4"
    run(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-noautorotate",
        "-ss",
        "5.000",
        "-t",
        "8.008",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-vf",
        (
            f"fps={FPS},"
            "scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,format=nv12"
        ),
        "-frames:v",
        "240",
        "-metadata:s:v:0",
        "rotate=0",
        "-an",
        *VIDEO,
        str(destination),
    )


def main() -> None:
    V10.mkdir(parents=True, exist_ok=True)
    build_clean_opening()
    build_horizontal_c129()


if __name__ == "__main__":
    main()
