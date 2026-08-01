#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT = Path("/Volumes/Untitled/Pyrenees Selfie Timelapse")
HEROES = PROJECT / "Runway Hero Clips"
PHOTO_SECTIONS = PROJECT / "exports" / ".selfie-review-v3"
EXPORTS = PROJECT / "exports"

FPS = 24
TRANSITION_SECONDS = 0.25


@dataclass(frozen=True)
class Variant:
    label: str
    photo_hold_factor: float
    output_name: str


VARIANTS = (
    Variant(
        label="50% longer photo holds",
        photo_hold_factor=1.5,
        output_name="pyrenees-selfie-timelapse-50-percent-slower.mp4",
    ),
    Variant(
        label="100% longer photo holds",
        photo_hold_factor=2.0,
        output_name="pyrenees-selfie-timelapse-100-percent-slower.mp4",
    ),
)


def probe(ffprobe: str, path: Path) -> dict[str, float | int]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_frames,r_frame_rate,width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    stream = payload["streams"][0]
    return {
        "duration": float(payload["format"]["duration"]),
        "frames": int(stream["nb_frames"]),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
    }


def retimed_duration(frame_count: int, factor: float) -> float:
    retimed_frames = int((frame_count - 1) * factor + 0.5) + 1
    return retimed_frames / FPS


def render_variant(
    ffmpeg: str,
    ffprobe: str,
    variant: Variant,
    start: Path,
    before_cigar: Path,
    cigar: Path,
    after_cigar: Path,
    ending: Path,
) -> dict[str, object]:
    source_probes = {
        "start": probe(ffprobe, start),
        "before_cigar": probe(ffprobe, before_cigar),
        "cigar": probe(ffprobe, cigar),
        "after_cigar": probe(ffprobe, after_cigar),
        "ending": probe(ffprobe, ending),
    }
    durations = {
        "start": float(source_probes["start"]["duration"]),
        "before_cigar": retimed_duration(
            int(source_probes["before_cigar"]["frames"]),
            variant.photo_hold_factor,
        ),
        "cigar": float(source_probes["cigar"]["duration"]),
        "after_cigar": retimed_duration(
            int(source_probes["after_cigar"]["frames"]),
            variant.photo_hold_factor,
        ),
        "ending": float(source_probes["ending"]["duration"]),
    }

    transition = TRANSITION_SECONDS
    offset_start_to_before_cigar = durations["start"] - transition
    duration_before_cigar = (
        durations["start"] + durations["before_cigar"] - transition
    )
    offset_into_cigar = duration_before_cigar - transition
    duration_through_cigar = duration_before_cigar + durations["cigar"] - transition
    offset_out_of_cigar = duration_through_cigar - transition
    duration_after_cigar = (
        duration_through_cigar + durations["after_cigar"] - transition
    )
    offset_into_ending = duration_after_cigar - transition

    factor = variant.photo_hold_factor
    filter_graph = (
        "[0:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[start];"
        "[1:v]scale=1080:1080:flags=lanczos,"
        f"setpts={factor}*(PTS-STARTPTS),fps=24,"
        "format=yuv420p[before_cigar];"
        "[2:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[cigar];"
        "[3:v]scale=1080:1080:flags=lanczos,"
        f"setpts={factor}*(PTS-STARTPTS),fps=24,"
        "format=yuv420p[after_cigar];"
        "[4:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[ending];"
        f"[start][before_cigar]xfade=transition=fade:duration={transition}:"
        f"offset={offset_start_to_before_cigar:.6f}[v1];"
        f"[v1][cigar]xfade=transition=fade:duration={transition}:"
        f"offset={offset_into_cigar:.6f}[v2];"
        f"[v2][after_cigar]xfade=transition=fade:duration={transition}:"
        f"offset={offset_out_of_cigar:.6f}[v3];"
        f"[v3][ending]xfade=transition=fade:duration={transition}:"
        f"offset={offset_into_ending:.6f}[out]"
    )

    output = EXPORTS / variant.output_name
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(start),
            "-i",
            str(before_cigar),
            "-i",
            str(cigar),
            "-i",
            str(after_cigar),
            "-i",
            str(ending),
            "-filter_complex",
            filter_graph,
            "-map",
            "[out]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "15",
            "-pix_fmt",
            "yuv420p",
            "-fps_mode",
            "cfr",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )

    output_probe = probe(ffprobe, output)
    expected_duration = sum(durations.values()) - transition * 4
    if abs(float(output_probe["duration"]) - expected_duration) > 0.2:
        raise RuntimeError(
            f"{variant.label} rendered to {output_probe['duration']:.3f}s; "
            f"expected about {expected_duration:.3f}s."
        )

    return {
        "label": variant.label,
        "photo_hold_factor": variant.photo_hold_factor,
        "output": str(output),
        "duration_seconds": output_probe["duration"],
        "frames": output_probe["frames"],
        "dimensions": [output_probe["width"], output_probe["height"]],
        "fps": FPS,
        "hero_clips_remain_at_natural_speed": True,
        "transition_seconds": transition,
    }


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and FFprobe are required.")

    start = HEROES / "01-START-runway.mp4"
    cigar = HEROES / "02-CIGAR-runway.mp4"
    ending = HEROES / "03-END-runway.mp4"
    before_cigar = PHOTO_SECTIONS / "before-cigar.mp4"
    after_cigar = PHOTO_SECTIONS / "after-cigar.mp4"
    for source in (start, before_cigar, cigar, after_cigar, ending):
        if not source.is_file() or source.stat().st_size == 0:
            raise RuntimeError(f"Missing source section: {source}")

    EXPORTS.mkdir(parents=True, exist_ok=True)
    reports = [
        render_variant(
            ffmpeg,
            ffprobe,
            variant,
            start,
            before_cigar,
            cigar,
            after_cigar,
            ending,
        )
        for variant in VARIANTS
    ]
    report_path = EXPORTS / "pyrenees-selfie-timelapse-pacing-comparison.json"
    report_path.write_text(
        json.dumps({"variants": reports}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"variants": reports}, indent=2))


if __name__ == "__main__":
    main()
