from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .config import bundled_resource_dir


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".3gp", ".webm"}
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
    has_audio: bool = False
    rotation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bundled_tool(name: str) -> str | None:
    override = os.environ.get("PYRENEES_SELECTS_MEDIA_BIN_DIR")
    roots = [Path(override).expanduser()] if override else []
    resources = bundled_resource_dir()
    if resources:
        roots.extend((resources / "bin", resources.parent / "Frameworks"))
    for root in roots:
        candidate = root / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
    return None


def require_media_tools() -> tuple[str, str]:
    ffmpeg = _bundled_tool("ffmpeg") or shutil.which("ffmpeg")
    ffprobe = _bundled_tool("ffprobe") or shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise MediaToolError("The bundled media tools could not be found. Reinstall Pyrenees Selects.")
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
        "-show_entries",
        "stream=codec_type,codec_name,width,height,avg_frame_rate:stream_tags=rotate:stream_side_data=rotation:format=duration:format_tags=creation_time",
        "-of", "json",
        str(resolved),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=45)
        payload = json.loads(result.stdout)
        streams = payload["streams"]
        stream = next(item for item in streams if item.get("codec_type") == "video")
        media_format = payload["format"]
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise MediaToolError(f"Could not inspect {resolved.name}: {exc}") from exc
    duration = float(media_format.get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise MediaToolError(f"Could not determine a positive duration for {resolved.name}.")
    side_data = stream.get("side_data_list") or []
    side_rotation = next((item.get("rotation") for item in side_data if item.get("rotation") is not None), None)
    tag_rotation = (stream.get("tags") or {}).get("rotate")
    try:
        rotation = int(round(float(side_rotation if side_rotation is not None else tag_rotation or 0))) % 360
    except (TypeError, ValueError):
        rotation = 0
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
        has_audio=any(item.get("codec_type") == "audio" for item in streams),
        rotation=rotation,
    )


def has_audio_stream(path: Path, ffprobe: str | None = None) -> bool:
    resolved = path.expanduser().resolve(strict=True)
    tool = ffprobe or require_media_tools()[1]
    command = [
        tool,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(resolved),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=45)
    except subprocess.SubprocessError as exc:
        raise MediaToolError(f"Could not inspect the audio in {resolved.name}.") from exc
    return result.stdout.strip() == "audio"


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


def render_review_clip(
    source: Path,
    destination: Path,
    start: float,
    duration: float,
    ffmpeg: str | None = None,
    timeout_seconds: float = 120,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    tool = ffmpeg or require_media_tools()[0]
    temporary = destination.with_suffix(".partial.mp4")
    temporary.unlink(missing_ok=True)
    command = [tool, "-v", "error"]
    if platform.system() == "Darwin":
        command.extend(["-hwaccel", "videotoolbox"])
    command.extend([
        "-ss", f"{start:.3f}", "-i", str(source),
        "-t", f"{duration:.3f}", "-an", "-vf", "scale=-2:360",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(temporary),
    ])
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)
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


def _filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _treated_spatial_filters(
    crop_scale: float,
    *,
    rotate_counterclockwise: bool = False,
    working_width: int = 640,
    working_height: int = 360,
) -> list[str]:
    filters: list[str] = []
    if not 0.5 <= crop_scale <= 1.0:
        raise ValueError("Crop scale must be between 0.5 and 1.0.")
    if rotate_counterclockwise:
        filters.append("transpose=2")
    if crop_scale < 0.999:
        filters.append(
            f"crop=trunc(iw*{crop_scale:.6f}/2)*2:trunc(ih*{crop_scale:.6f}/2)*2:(iw-ow)/2:(ih-oh)/2"
        )
    filters.extend([
        f"scale={working_width}:{working_height}:force_original_aspect_ratio=decrease",
        f"pad={working_width}:{working_height}:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
    ])
    return filters


def treatment_filter_chain(
    playback_rate: float,
    crop_scale: float = 1.0,
    contrast: float = 1.0,
    saturation: float | None = None,
    motion_interpolation: bool = False,
    stabilization_transform: Path | None = None,
    rotate_counterclockwise: bool = False,
    zoom_strength: float = 0.0,
    zoom_center_x: float = 0.5,
    zoom_center_y: float = 0.5,
    output_duration: float | None = None,
) -> str:
    if not 0.25 <= playback_rate <= 8.0:
        raise ValueError("Playback rate must be between 0.25× and 8×.")
    if not 0.8 <= contrast <= 1.3:
        raise ValueError("Contrast must be between 0.8 and 1.3.")
    effective_saturation = 1.03 if saturation is None and abs(contrast - 1.0) > 0.001 else (saturation or 1.0)
    if not 0.5 <= effective_saturation <= 2.0:
        raise ValueError("Saturation must be between 0.5 and 2.0.")
    if not 0.0 <= zoom_strength <= 1.5:
        raise ValueError("Zoom strength must be between 0 and 1.5.")
    if not 0.0 <= zoom_center_x <= 1.0 or not 0.0 <= zoom_center_y <= 1.0:
        raise ValueError("Zoom center coordinates must be between 0 and 1.")
    if zoom_strength and (output_duration is None or output_duration <= 0):
        raise ValueError("A positive output duration is required for an eased zoom.")
    if zoom_strength and stabilization_transform is not None:
        raise ValueError("Eased zoom and stabilization cannot be combined in the same review render.")
    working_width, working_height = ((1280, 720) if zoom_strength else (640, 360))
    filters = _treated_spatial_filters(
        crop_scale,
        rotate_counterclockwise=rotate_counterclockwise,
        working_width=working_width,
        working_height=working_height,
    )
    if stabilization_transform is not None:
        filters.append(
            "vidstabtransform="
            f"input='{_filter_path(stabilization_transform)}':smoothing=10:optzoom=1:interpol=bicubic"
        )
    if abs(contrast - 1.0) > 0.001 or abs(effective_saturation - 1.0) > 0.001:
        filters.append(f"eq=contrast={contrast:.4f}:saturation={effective_saturation:.4f}")
    if motion_interpolation:
        filters.append("minterpolate=fps=50:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    filters.extend([
        f"setpts=(PTS-STARTPTS)/{playback_rate:.6f}",
        "fps=25",
    ])
    if zoom_strength:
        output_frames = max(2, round(float(output_duration) * 25))
        filters.append(
            "zoompan="
            f"z='1+{zoom_strength:.6f}*sin(PI*on/{output_frames - 1})':"
            f"x='iw*{zoom_center_x:.6f}-iw/(2*zoom)':"
            f"y='ih*{zoom_center_y:.6f}-ih/(2*zoom)':"
            "d=1:s=640x360:fps=25"
        )
    filters.append("format=yuv420p")
    return ",".join(filters)


def _treated_input_command(tool: str, source: Path, start: float, duration: float) -> list[str]:
    command = [tool, "-v", "error"]
    if platform.system() == "Darwin":
        command.extend(["-hwaccel", "videotoolbox"])
    command.extend(["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source)])
    return command


def _atempo_filter_chain(playback_rate: float) -> list[str]:
    if not 0.25 <= playback_rate <= 8.0:
        raise ValueError("Audio playback rate must be between 0.25× and 8×.")
    remaining = playback_rate
    factors: list[float] = []
    while remaining < 0.5 - 0.000001:
        factors.append(0.5)
        remaining /= 0.5
    while remaining > 2.0 + 0.000001:
        factors.append(2.0)
        remaining /= 2.0
    if abs(remaining - 1.0) > 0.000001:
        factors.append(remaining)
    return [f"atempo={factor:.6f}" for factor in factors]


def render_treated_clip(
    source: Path,
    destination: Path,
    start: float,
    duration: float,
    *,
    playback_rate: float = 1.0,
    stabilize: bool = False,
    crop_scale: float = 1.0,
    contrast: float = 1.0,
    saturation: float | None = None,
    motion_interpolation: bool = False,
    rotate_counterclockwise: bool = False,
    zoom_strength: float = 0.0,
    zoom_center_x: float = 0.5,
    zoom_center_y: float = 0.5,
    include_audio: bool = False,
    audio_playback_rate: float | None = None,
    target_duration: float | None = None,
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
    timeout_seconds: float = 900,
) -> Path:
    if start < 0 or duration <= 0:
        raise ValueError("Treated source ranges must have a non-negative start and positive duration.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    tool = ffmpeg or require_media_tools()[0]
    output_duration = target_duration if target_duration is not None else duration / playback_rate
    if output_duration <= 0:
        raise ValueError("Treated output duration must be positive.")
    temporary = destination.with_suffix(".partial.mp4")
    transform = destination.with_suffix(".transform.trf")
    temporary.unlink(missing_ok=True)
    transform.unlink(missing_ok=True)
    try:
        if stabilize:
            detect_filter = ",".join(
                _treated_spatial_filters(
                    crop_scale,
                    rotate_counterclockwise=rotate_counterclockwise,
                )
                + [
                    "vidstabdetect="
                    f"shakiness=4:accuracy=9:stepsize=6:mincontrast=0.25:result='{_filter_path(transform)}'"
                ]
            )
            detect_command = _treated_input_command(tool, source, start, duration)
            detect_command.extend(["-an", "-vf", detect_filter, "-f", "null", "-"])
            subprocess.run(detect_command, check=True, capture_output=True, timeout=timeout_seconds)
        render_filter = treatment_filter_chain(
            playback_rate,
            crop_scale,
            contrast,
            saturation,
            motion_interpolation,
            transform if stabilize else None,
            rotate_counterclockwise,
            zoom_strength,
            zoom_center_x,
            zoom_center_y,
            output_duration,
        )
        command = _treated_input_command(tool, source, start, duration)
        if include_audio:
            if has_audio_stream(source, ffprobe=ffprobe):
                audio_rate = audio_playback_rate if audio_playback_rate is not None else playback_rate
                audio_filters = _atempo_filter_chain(audio_rate)
                audio_filters.extend([
                    "aresample=48000",
                    "aformat=sample_fmts=fltp:channel_layouts=stereo",
                    f"apad=whole_dur={output_duration:.6f}",
                    f"atrim=duration={output_duration:.6f}",
                    "asetpts=PTS-STARTPTS",
                ])
                audio_chain = "[0:a:0]" + ",".join(audio_filters) + "[a]"
            else:
                audio_chain = f"anullsrc=r=48000:cl=stereo:d={output_duration:.6f}[a]"
            command.extend([
                "-filter_complex", f"[0:v:0]{render_filter}[v];{audio_chain}",
                "-map", "[v]", "-map", "[a]",
                "-t", f"{output_duration:.6f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                "-c:a", "aac", "-b:a", "128k",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(temporary),
            ])
        else:
            command.extend([
                "-an", "-vf", render_filter,
                "-t", f"{output_duration:.6f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(temporary),
            ])
        subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)
        temporary.replace(destination)
    except subprocess.SubprocessError as exc:
        temporary.unlink(missing_ok=True)
        raise MediaToolError(f"Could not create treated clip for {source.name}.") from exc
    finally:
        transform.unlink(missing_ok=True)
    return destination


def concatenate_video_clips(
    clips: Sequence[Path],
    destination: Path,
    ffmpeg: str | None = None,
    timeout_seconds: float = 300,
) -> Path:
    if not clips:
        raise ValueError("At least one treated clip is required.")
    resolved = [clip.resolve(strict=True) for clip in clips]
    if any("'" in str(clip) for clip in resolved):
        raise ValueError("Treated clip paths cannot contain apostrophes.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    tool = ffmpeg or require_media_tools()[0]
    temporary = destination.with_suffix(".partial.mp4")
    temporary.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="pyrenees-concat-") as directory:
        concat_list = Path(directory) / "clips.txt"
        concat_list.write_text(
            "".join(f"file '{clip}'\n" for clip in resolved),
            encoding="utf-8",
        )
        command = [
            tool, "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", "-movflags", "+faststart", "-y", str(temporary),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)
            temporary.replace(destination)
        except subprocess.SubprocessError as exc:
            temporary.unlink(missing_ok=True)
            raise MediaToolError("Could not assemble the treated rough cut.") from exc
    return destination
