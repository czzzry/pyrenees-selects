from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg"}


class MediaToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoMetadata:
    path: str
    filename: str
    captured_at: str
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def require_media_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise MediaToolError("ffmpeg and ffprobe are required and must be available on PATH.")
    return ffmpeg, ffprobe


def _fraction(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    numerator, _, denominator = value.partition("/")
    if denominator:
        return float(numerator) / float(denominator)
    return float(value)


def _capture_time(path: Path, tags: dict[str, Any]) -> str:
    raw = tags.get("creation_time")
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
    stem_parts = path.stem.split("_")
    if len(stem_parts) > 1 and len(stem_parts[1]) == 14 and stem_parts[1].isdigit():
        return datetime.strptime(stem_parts[1], "%Y%m%d%H%M%S").isoformat()
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()


def probe_video(path: Path, ffprobe: str | None = None) -> VideoMetadata:
    resolved = path.expanduser().resolve(strict=True)
    tool = ffprobe or require_media_tools()[1]
    command = [
        tool,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate:format=duration:format_tags=creation_time",
        "-of", "json",
        str(resolved),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=45)
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        media_format = payload["format"]
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise MediaToolError(f"Could not inspect {resolved.name}: {exc}") from exc
    duration = float(media_format.get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise MediaToolError(f"Could not determine a positive duration for {resolved.name}.")
    return VideoMetadata(
        path=str(resolved),
        filename=resolved.name,
        captured_at=_capture_time(resolved, media_format.get("tags") or {}),
        duration=duration,
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        fps=_fraction(stream.get("avg_frame_rate")),
        codec=str(stream.get("codec_name") or "unknown"),
        size_bytes=resolved.stat().st_size,
    )


def top_level_videos(source_dir: Path) -> list[Path]:
    root = source_dir.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    return sorted(
        (path for path in root.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda path: path.name.lower(),
    )


def candidate_range(duration: float, target_duration: float = 8.0) -> tuple[float, float]:
    if duration <= 0:
        raise ValueError("duration must be positive")
    usable_duration = min(target_duration, max(2.0, duration))
    if duration <= usable_duration:
        return 0.0, duration
    start = max(0.0, duration * 0.40 - usable_duration / 2)
    return min(start, duration - usable_duration), usable_duration


def cache_key(source: Path, start: float, duration: float, kind: str) -> str:
    stat = source.stat()
    identity = f"{source.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{start:.3f}|{duration:.3f}|{kind}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def render_review_clip(source: Path, destination: Path, start: float, duration: float, ffmpeg: str | None = None) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    tool = ffmpeg or require_media_tools()[0]
    temporary = destination.with_suffix(".partial.mp4")
    temporary.unlink(missing_ok=True)
    command = [
        tool, "-v", "error", "-ss", f"{start:.3f}", "-i", str(source),
        "-t", f"{duration:.3f}", "-an", "-vf", "scale=-2:360",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(temporary),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=120)
        temporary.replace(destination)
    except subprocess.SubprocessError as exc:
        temporary.unlink(missing_ok=True)
        raise MediaToolError(f"Could not create review clip for {source.name}.") from exc
    return destination


def render_context_frame(source: Path, destination: Path, timestamp: float, ffmpeg: str | None = None) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    tool = ffmpeg or require_media_tools()[0]
    temporary = destination.with_suffix(".partial.jpg")
    temporary.unlink(missing_ok=True)
    command = [
        tool, "-v", "error", "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(source),
        "-frames:v", "1", "-vf", "scale=-2:360", "-q:v", "5", "-y", str(temporary),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=60)
        temporary.replace(destination)
    except subprocess.SubprocessError as exc:
        temporary.unlink(missing_ok=True)
        raise MediaToolError(f"Could not create context frame for {source.name}.") from exc
    return destination
