#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


PROJECT = Path("/Volumes/Untitled/Pyrenees Selfie Timelapse")
ALIGNED = PROJECT / "analysis" / "face-aligned-v1" / "aligned"
HEROES = PROJECT / "Runway Hero Clips"
EXPORTS = PROJECT / "exports"
WORK = EXPORTS / ".selfie-review-v3"
OUTPUT = EXPORTS / "pyrenees-selfie-timelapse-review-v3.mp4"

FPS = 24
FRAMES_PER_PHOTO = 5
TRANSITION_SECONDS = 0.25
EXPECTED_PHOTOS = 305
CIGAR_PHOTO_NAME = "205-PXL_20240708_150405326.jpg"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def probe_duration(ffprobe: str, path: Path) -> float:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def quote_concat_path(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def write_concat_manifest(destination: Path, photos: list[Path]) -> None:
    duration = FRAMES_PER_PHOTO / FPS
    lines = ["ffconcat version 1.0"]
    for photo in photos:
        lines.append(f"file '{quote_concat_path(photo)}'")
        lines.append(f"duration {duration:.12f}")
    # FFmpeg needs the final frame repeated for its duration to take effect.
    lines.append(f"file '{quote_concat_path(photos[-1])}'")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_photo_section(ffmpeg: str, manifest: Path, destination: Path) -> None:
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-vf",
            f"fps={FPS},scale=1080:1080:flags=lanczos,format=yuv420p",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "12",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg and FFprobe are required.")

    photos = sorted(
        photo for photo in ALIGNED.glob("*.jpg") if not photo.name.startswith("._")
    )
    if len(photos) != EXPECTED_PHOTOS:
        raise RuntimeError(
            f"Expected {EXPECTED_PHOTOS} aligned photos, found {len(photos)}."
        )

    start = HEROES / "01-START-runway.mp4"
    cigar = HEROES / "02-CIGAR-runway.mp4"
    ending = HEROES / "03-END-runway.mp4"
    for clip in (start, cigar, ending):
        if not clip.is_file():
            raise RuntimeError(f"Missing hero clip: {clip}")

    EXPORTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    cigar_matches = [index for index, photo in enumerate(photos) if photo.name == CIGAR_PHOTO_NAME]
    if len(cigar_matches) != 1:
        raise RuntimeError(
            f"Expected one aligned cigar source named {CIGAR_PHOTO_NAME}, "
            f"found {len(cigar_matches)}."
        )
    cigar_index = cigar_matches[0]
    before_cigar_photos = photos[:cigar_index]
    after_cigar_photos = photos[cigar_index + 1 :]
    before_cigar_manifest = WORK / "before-cigar.ffconcat"
    after_cigar_manifest = WORK / "after-cigar.ffconcat"
    before_cigar_video = WORK / "before-cigar.mp4"
    after_cigar_video = WORK / "after-cigar.mp4"
    write_concat_manifest(before_cigar_manifest, before_cigar_photos)
    write_concat_manifest(after_cigar_manifest, after_cigar_photos)
    render_photo_section(ffmpeg, before_cigar_manifest, before_cigar_video)
    render_photo_section(ffmpeg, after_cigar_manifest, after_cigar_video)

    durations = {
        "start": probe_duration(ffprobe, start),
        "before_cigar": probe_duration(ffprobe, before_cigar_video),
        "cigar": probe_duration(ffprobe, cigar),
        "after_cigar": probe_duration(ffprobe, after_cigar_video),
        "ending": probe_duration(ffprobe, ending),
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

    filter_graph = (
        "[0:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[start];"
        "[1:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[before_cigar];"
        "[2:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[cigar];"
        "[3:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[after_cigar];"
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

    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(start),
            "-i",
            str(before_cigar_video),
            "-i",
            str(cigar),
            "-i",
            str(after_cigar_video),
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
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ]
    )

    final_duration = probe_duration(ffprobe, OUTPUT)
    expected_duration = sum(durations.values()) - transition * 4
    if abs(final_duration - expected_duration) > 0.15:
        raise RuntimeError(
            f"Unexpected final duration: {final_duration:.3f}s "
            f"(expected {expected_duration:.3f}s)."
        )

    report = {
        "output": str(OUTPUT),
        "duration_seconds": final_duration,
        "fps": FPS,
        "dimensions": [1080, 1080],
        "reviewed_photo_count": len(photos),
        "rendered_still_photo_count": len(photos) - 1,
        "frames_per_photo": FRAMES_PER_PHOTO,
        "seconds_per_photo": FRAMES_PER_PHOTO / FPS,
        "cigar_source_photo_replaced_by_animation": CIGAR_PHOTO_NAME,
        "before_cigar_photo_count": len(before_cigar_photos),
        "after_cigar_photo_count": len(after_cigar_photos),
        "hero_clips": {
            "start": str(start),
            "cigar": str(cigar),
            "ending": str(ending),
        },
        "transition_seconds": transition,
        "section_durations": durations,
    }
    (EXPORTS / "pyrenees-selfie-timelapse-review-v3.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
