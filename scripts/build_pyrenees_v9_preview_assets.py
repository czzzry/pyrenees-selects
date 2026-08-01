#!/usr/bin/env python3
"""Build six simple 4K phone inserts for the Extended Cut v9 viewing pass."""

from __future__ import annotations

import subprocess
from pathlib import Path


PHONE = Path(
    "/Users/cezarybaraniecki/Documents/AI project/AI Video Editor/"
    "raw_footage/phone_pyrenees_2024"
)
OUT = Path(
    "/Users/cezarybaraniecki/Library/Application Support/"
    "Pyrenees Selects/revisions_v9"
)
FPS = "30000/1001"

CLIPS = (
    ("C92-18to26-v9.mp4", "PXL_20240613_103400024.mp4", 18.0, False),
    ("C105-04to12-v9.mp4", "PXL_20240614_152820904.mp4", 4.0, False),
    ("C111-morning-04to12-rosy-v9.mp4", "PXL_20240615_052909649.mp4", 4.0, True),
    ("C115-08to16-v9.mp4", "PXL_20240615_101435912.mp4", 8.0, False),
    ("C128-00to08-v9.mp4", "PXL_20240617_065921987.mp4", 0.0, False),
    # PXL_...072939772 is only 0.60 s. This is its continuation, recorded
    # two seconds later, spanning the map/rocks-to-mountain camera move.
    ("C129-continuation-05to13-v9.mp4", "PXL_20240617_072941884.mp4", 5.0, False),
)


def build(output_name: str, source_name: str, start: float, rosy: bool) -> None:
    source = PHONE / source_name
    destination = OUT / output_name
    if not source.exists():
        raise FileNotFoundError(source)

    filters = [
        f"fps={FPS}",
        "scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos",
        "pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=black",
        "setsar=1",
    ]
    if rosy:
        # A restrained dawn grade: modest color separation and warmth without
        # forcing magenta into the neutral rocks or clipping the bright sky.
        filters.extend(
            [
                "eq=contrast=1.04:saturation=1.13:brightness=0.008:gamma=1.015",
                "colorchannelmixer=rr=1.035:gg=1.008:bb=0.975",
            ]
        )
    filters.append("format=nv12")

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-hwaccel",
            "videotoolbox",
            "-ss",
            f"{start:.3f}",
            "-t",
            "8.008",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-vf",
            ",".join(filters),
            "-frames:v",
            "240",
            "-an",
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
            str(destination),
        ],
        check=True,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in CLIPS:
        print(f"Building {spec[0]}", flush=True)
        build(*spec)


if __name__ == "__main__":
    main()
