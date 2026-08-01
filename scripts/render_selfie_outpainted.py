#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


PROJECT = Path("/Volumes/Untitled/Pyrenees Selfie Timelapse")
ALIGNED = PROJECT / "analysis" / "face-aligned-v1" / "aligned"
OUTPAINTED = PROJECT / "analysis" / "outpaint-v1" / "generated-jpeg"
HEROES = PROJECT / "Runway Hero Clips"
EXPORTS = PROJECT / "exports"
WORK = EXPORTS / ".selfie-outpainted-50-percent-slower"
OUTPUT = EXPORTS / "pyrenees-selfie-timelapse-50-percent-slower-outpainted.mp4"
REPORT = EXPORTS / "pyrenees-selfie-timelapse-50-percent-slower-outpainted.json"

FPS = 24
FRAMES_PER_PHOTO = 7.5
TRANSITION_SECONDS = 0.25
EXPECTED_PHOTOS = 305
EXPECTED_OUTPAINTED = 42
CIGAR_PHOTO_NAME = "205-PXL_20240708_150405326.jpg"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


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
        "fps": stream["r_frame_rate"],
    }


def quote_concat_path(path: Path) -> str:
    return str(path).replace("'", "'\\''")


def write_concat_manifest(destination: Path, photos: list[Path]) -> None:
    duration = FRAMES_PER_PHOTO / FPS
    lines = ["ffconcat version 1.0"]
    for photo in photos:
        lines.append(f"file '{quote_concat_path(photo)}'")
        lines.append(f"duration {duration:.12f}")
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

    aligned = sorted(
        photo for photo in ALIGNED.glob("*.jpg") if not photo.name.startswith("._")
    )
    if len(aligned) != EXPECTED_PHOTOS:
        raise RuntimeError(
            f"Expected {EXPECTED_PHOTOS} aligned photos, found {len(aligned)}."
        )

    outpainted = {
        photo.stem: photo
        for photo in OUTPAINTED.glob("*.jpg")
        if not photo.name.startswith("._")
    }
    if len(outpainted) != EXPECTED_OUTPAINTED:
        raise RuntimeError(
            f"Expected {EXPECTED_OUTPAINTED} outpainted photos, "
            f"found {len(outpainted)}."
        )

    photos = [outpainted.get(photo.stem, photo) for photo in aligned]
    substitutions = sum(photo.parent == OUTPAINTED for photo in photos)
    if substitutions != EXPECTED_OUTPAINTED:
        raise RuntimeError(
            f"Expected {EXPECTED_OUTPAINTED} substitutions, found {substitutions}."
        )

    start = HEROES / "01-START-runway.mp4"
    cigar = HEROES / "02-CIGAR-runway.mp4"
    ending = HEROES / "03-END-runway.mp4"
    for clip in (start, cigar, ending):
        if not clip.is_file() or clip.stat().st_size == 0:
            raise RuntimeError(f"Missing hero clip: {clip}")

    cigar_index = next(
        (index for index, photo in enumerate(aligned) if photo.name == CIGAR_PHOTO_NAME),
        None,
    )
    if cigar_index is None:
        raise RuntimeError(f"Missing cigar source photo: {CIGAR_PHOTO_NAME}")

    EXPORTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    before_photos = photos[:cigar_index]
    after_photos = photos[cigar_index + 1 :]
    before_manifest = WORK / "before-cigar.ffconcat"
    after_manifest = WORK / "after-cigar.ffconcat"
    before_video = WORK / "before-cigar.mp4"
    after_video = WORK / "after-cigar.mp4"
    write_concat_manifest(before_manifest, before_photos)
    write_concat_manifest(after_manifest, after_photos)
    render_photo_section(ffmpeg, before_manifest, before_video)
    render_photo_section(ffmpeg, after_manifest, after_video)

    durations = {
        "start": float(probe(ffprobe, start)["duration"]),
        "before_cigar": float(probe(ffprobe, before_video)["duration"]),
        "cigar": float(probe(ffprobe, cigar)["duration"]),
        "after_cigar": float(probe(ffprobe, after_video)["duration"]),
        "ending": float(probe(ffprobe, ending)["duration"]),
    }
    transition = TRANSITION_SECONDS
    offset_1 = durations["start"] - transition
    through_before = durations["start"] + durations["before_cigar"] - transition
    offset_2 = through_before - transition
    through_cigar = through_before + durations["cigar"] - transition
    offset_3 = through_cigar - transition
    through_after = through_cigar + durations["after_cigar"] - transition
    offset_4 = through_after - transition

    filter_graph = (
        "[0:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[start];"
        "[1:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[before];"
        "[2:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[cigar];"
        "[3:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[after];"
        "[4:v]scale=1080:1080:flags=lanczos,fps=24,"
        "format=yuv420p,setpts=PTS-STARTPTS[end];"
        f"[start][before]xfade=transition=fade:duration={transition}:"
        f"offset={offset_1:.6f}[v1];"
        f"[v1][cigar]xfade=transition=fade:duration={transition}:"
        f"offset={offset_2:.6f}[v2];"
        f"[v2][after]xfade=transition=fade:duration={transition}:"
        f"offset={offset_3:.6f}[v3];"
        f"[v3][end]xfade=transition=fade:duration={transition}:"
        f"offset={offset_4:.6f}[out]"
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
            str(before_video),
            "-i",
            str(cigar),
            "-i",
            str(after_video),
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
            str(OUTPUT),
        ]
    )

    output_probe = probe(ffprobe, OUTPUT)
    expected_duration = sum(durations.values()) - transition * 4
    if abs(float(output_probe["duration"]) - expected_duration) > 0.2:
        raise RuntimeError(
            f"Rendered {output_probe['duration']:.3f}s; "
            f"expected about {expected_duration:.3f}s."
        )
    if (
        output_probe["width"] != 1080
        or output_probe["height"] != 1080
        or output_probe["fps"] != "24/1"
    ):
        raise RuntimeError(f"Unexpected output format: {output_probe}")

    report = {
        "output": str(OUTPUT),
        "duration_seconds": output_probe["duration"],
        "frames": output_probe["frames"],
        "fps": FPS,
        "dimensions": [1080, 1080],
        "source_photo_count": len(photos),
        "rendered_still_photo_count": len(photos) - 1,
        "outpainted_photo_count": substitutions,
        "unaltered_aligned_photo_count": len(photos) - substitutions,
        "photo_hold_factor": 1.5,
        "seconds_per_photo": FRAMES_PER_PHOTO / FPS,
        "hero_clips_remain_at_natural_speed": True,
        "cigar_source_photo_replaced_by_animation": CIGAR_PHOTO_NAME,
        "transition_seconds": transition,
        "section_durations": durations,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
