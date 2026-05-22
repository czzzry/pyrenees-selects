from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import os
import random
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import streamlit as st

from processor import export_remote_job_package


ROOT = Path(__file__).parent
RAW_DIR = ROOT / "raw_footage"
MUSIC_DIR = ROOT / "music"
MUSIC_LIBRARY_DIR = ROOT / "music_library"
CACHE_DIR = ROOT / "cache"
ANALYSIS_CACHE_DIR = CACHE_DIR / "analysis_cache"
OUTPUT_DIR = ROOT / "outputs"
SELECTED_DIR = OUTPUT_DIR / "selected_clips"
THUMBNAIL_DIR = OUTPUT_DIR / "thumbnails"
TEMP_DIR = OUTPUT_DIR / "temp"
MUST_REVIEW_DIR = OUTPUT_DIR / "must_review_clips"
SUBJECT_FOCUS_DIR = OUTPUT_DIR / "subject_focus_clips"
STATUS_PATH = OUTPUT_DIR / "job_status.json"
CONFIG_PATH = OUTPUT_DIR / "job_config.json"
RUN_LOG_PATH = OUTPUT_DIR / "run_log.txt"
PERFORMANCE_CSV_PATH = OUTPUT_DIR / "performance_report.csv"
PERFORMANCE_TXT_PATH = OUTPUT_DIR / "performance_report.txt"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
STAGES = [
    "Scanning videos",
    "Generating thumbnails",
    "Analyzing frames",
    "Scoring candidate segments",
    "Selecting final clips",
    "Rendering clips",
    "Assembling rough cut",
    "Exporting final video",
    "Done",
]


@dataclass(frozen=True)
class DependencyInfo:
    ffmpeg: str | None
    ffprobe: str | None
    ffmpeg_source: str
    ffprobe_source: str


@dataclass(frozen=True)
class ClipInfo:
    path: Path
    duration: float
    fps: float
    width: int
    height: int
    size_mb: float
    modified: float


@dataclass
class Candidate:
    source: Path
    start: float
    end: float
    duration: float
    score: float
    motion: float
    sharpness: float
    stability: float
    variety: float
    thumb_time: float
    hist: np.ndarray
    reason: str = ""
    rejection_reason: str = ""
    subject_hint: bool = False
    subject_x: float = 0.5
    subject_y: float = 0.5


def ensure_dirs() -> None:
    for folder in (RAW_DIR, MUSIC_DIR, MUSIC_LIBRARY_DIR, CACHE_DIR, ANALYSIS_CACHE_DIR, OUTPUT_DIR, SELECTED_DIR, THUMBNAIL_DIR, TEMP_DIR, MUST_REVIEW_DIR, SUBJECT_FOCUS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def detect_dependencies() -> DependencyInfo:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    ffmpeg_source = "system PATH" if ffmpeg else "not found"
    ffprobe_source = "system PATH" if ffprobe else "not found"
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            ffmpeg_source = "imageio-ffmpeg fallback"
        except Exception:
            pass
    return DependencyInfo(ffmpeg=ffmpeg, ffprobe=ffprobe, ffmpeg_source=ffmpeg_source, ffprobe_source=ffprobe_source)


def is_inside_venv(path: Path) -> bool:
    return ".venv" in path.expanduser().parts


def video_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists() or not source_dir.is_dir() or is_inside_venv(source_dir):
        return []
    return sorted(p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)


def audio_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists() or not source_dir.is_dir():
        return []
    return sorted(p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)


@st.cache_data(show_spinner=False, ttl=60)
def scan_music_library_cached(root: str, signature: str) -> list[str]:
    base = Path(root)
    if not base.exists():
        return []
    tracks: list[str] = []
    for current, dirs, files in os.walk(base, followlinks=True):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".git"]
        current_path = Path(current)
        if any(part.startswith(".") or part == ".git" for part in current_path.relative_to(base).parts):
            continue
        for filename in files:
            if filename.startswith("."):
                continue
            path = current_path / filename
            if path.suffix.lower() in AUDIO_EXTENSIONS:
                tracks.append(str(path))
    return sorted(set(tracks))


def music_library_signature() -> str:
    if not MUSIC_LIBRARY_DIR.exists():
        return "missing"
    latest = 0
    count = 0
    for current, dirs, files in os.walk(MUSIC_LIBRARY_DIR, followlinks=True):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".git"]
        for filename in files:
            if filename.startswith("."):
                continue
            path = Path(current) / filename
            if path.suffix.lower() in AUDIO_EXTENSIONS or path.name == "music_library.csv":
                try:
                    stat = path.stat()
                except OSError:
                    continue
                latest = max(latest, stat.st_mtime_ns)
                count += 1
    return f"{count}:{latest}"


def music_library_tracks() -> list[Path]:
    return [Path(path) for path in scan_music_library_cached(str(MUSIC_LIBRARY_DIR), music_library_signature())]


def is_valid_audio_file(path: Path) -> bool:
    return path.exists() and path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def open_folder(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])


def append_music_metadata(row: dict[str, str]) -> None:
    MUSIC_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = MUSIC_LIBRARY_DIR / "music_library.csv"
    fieldnames = ["filename", "title", "artist", "mood", "bpm", "license", "source_url", "attribution_required", "attribution_text"]
    exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fieldnames})


def import_music_from_url(url: str, metadata: dict[str, str]) -> Path:
    parsed = urllib.parse.urlparse(url.strip())
    filename = Path(urllib.parse.unquote(parsed.path)).name
    suffix = Path(filename).suffix.lower()
    if parsed.scheme not in {"https", "http"} or suffix not in AUDIO_EXTENSIONS:
        raise ValueError("Use a direct http(s) URL ending in .mp3, .wav, .m4a, .flac, or .ogg.")
    target = MUSIC_LIBRARY_DIR / filename
    if target.exists():
        stem = target.stem
        target = MUSIC_LIBRARY_DIR / f"{stem}_{int(time.time())}{target.suffix}"
    request = urllib.request.Request(url, headers={"User-Agent": "local-drone-rough-cut/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get("content-type", "")
        if "audio" not in content_type and suffix not in AUDIO_EXTENSIONS:
            raise ValueError("The URL does not appear to point to an audio file.")
        target.write_bytes(response.read())
    row = dict(metadata)
    row["filename"] = target.name
    row["source_url"] = url
    append_music_metadata(row)
    return target


def open_system_folder_picker() -> str | None:
    if sys.platform == "darwin":
        result = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select drone footage folder")'],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(title="Select drone footage folder")
    root.destroy()
    return selected or None


def open_system_file_picker() -> str | None:
    if sys.platform == "darwin":
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'POSIX path of (choose file with prompt "Select music file" of type {"mp3","wav","m4a","flac","ogg"})',
            ],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askopenfilename(title="Select music file", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.flac *.ogg")])
    root.destroy()
    return selected or None


def run_command(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Unknown ffmpeg error."
        raise RuntimeError(message)


def command_output(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    except Exception:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return (result.stdout or result.stderr).strip()


def probe_duration(path: Path, ffprobe_path: str | None) -> float | None:
    if not ffprobe_path:
        return None
    result = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def inspect_clip(path: Path, ffprobe_path: str | None = None) -> ClipInfo | None:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration = probe_duration(path, ffprobe_path) or (frame_count / fps if fps > 0 else 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    if duration <= 0 or width <= 0 or height <= 0:
        return None
    stat = path.stat()
    return ClipInfo(path=path, duration=duration, fps=fps, width=width, height=height, size_mb=stat.st_size / (1024 * 1024), modified=stat.st_mtime)


def thumbnail_cache_path(path: Path) -> Path:
    stat = path.stat()
    key = f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return THUMBNAIL_DIR / f"{digest}.jpg"


def placeholder_thumbnail() -> str:
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    placeholder = THUMBNAIL_DIR / "placeholder.jpg"
    if not placeholder.exists():
        image = np.full((90, 160, 3), 42, dtype=np.uint8)
        cv2.rectangle(image, (2, 2), (157, 87), (90, 90, 90), 1)
        cv2.putText(image, "No preview", (34, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (210, 210, 210), 1, cv2.LINE_AA)
        cv2.imwrite(str(placeholder), image)
    return image_data_uri(placeholder)


def image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def generate_video_thumbnail(path: Path, info: ClipInfo | None) -> str:
    try:
        cached = thumbnail_cache_path(path)
        if cached.exists():
            return image_data_uri(cached)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return placeholder_thumbnail()
        fps = cap.get(cv2.CAP_PROP_FPS) or (info.fps if info else 30)
        duration = info.duration if info else 0
        sample_time = max(0.0, min(duration * 0.10, duration / 2)) if duration > 0 else 0.0
        frame = read_frame(cap, sample_time, fps)
        cap.release()
        if frame is None:
            return placeholder_thumbnail()
        thumb = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(cached), thumb)
        return image_data_uri(cached)
    except Exception:
        return placeholder_thumbnail()


def read_frame(cap: cv2.VideoCapture, time_s: float, fps: float) -> np.ndarray | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(time_s * fps)))
    ok, frame = cap.read()
    return frame if ok else None


def frame_hist(frame: np.ndarray) -> np.ndarray:
    small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    return cv2.normalize(hist, hist).flatten().astype(np.float32)


def sharpness_score(frame: np.ndarray) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def motion_score(previous: np.ndarray | None, frame: np.ndarray) -> float:
    if previous is None:
        return 0.0
    prev = cv2.resize(previous, (160, 90), interpolation=cv2.INTER_AREA)
    curr = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    return float(np.mean(cv2.absdiff(cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY), cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY))))


def normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    low = float(np.percentile(values, 5))
    high = float(np.percentile(values, 95))
    if math.isclose(low, high):
        return [0.5 for _ in values]
    return [float(np.clip((value - low) / (high - low), 0, 1)) for value in values]


def write_status(stage: str, progress: int, status: str = "running", message: str = "", started_at: float | None = None) -> None:
    current = read_status()
    start = started_at or float(current.get("started_at") or time.time())
    elapsed = max(0.0, time.time() - start)
    eta = None
    if progress > 2 and status == "running":
        eta = max(0.0, elapsed * ((100 - progress) / progress))
    payload = {
        "status": status,
        "stage": stage,
        "progress": progress,
        "message": message,
        "started_at": start,
        "elapsed": elapsed,
        "eta": eta,
        "updated_at": time.time(),
    }
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_status() -> dict[str, Any]:
    if not STATUS_PATH.exists():
        return {}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def append_log(message: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%H:%M:%S")
    with RUN_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def clean_partial_outputs() -> None:
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    for path in SELECTED_DIR.glob("*.mp4"):
        path.unlink(missing_ok=True)
    for path in TEMP_DIR.glob("*"):
        if path.is_file():
            path.unlink(missing_ok=True)
    for name in [
        "rough_cut.mp4",
        "rough_cut_preview.mp4",
        "rough_cut_silent.mp4",
        "rejected_segments.csv",
        "edit_decisions.csv",
        "contact_sheet.jpg",
        "music_used.txt",
        "performance_report.csv",
        "performance_report.txt",
    ]:
        (OUTPUT_DIR / name).unlink(missing_ok=True)


def available_memory_gb() -> float | None:
    if sys.platform == "darwin":
        page_size_output = command_output(["sysctl", "-n", "hw.pagesize"])
        vm_output = command_output(["vm_stat"])
        try:
            page_size = int(page_size_output)
            available_pages = 0
            for line in vm_output.splitlines():
                if line.startswith(("Pages free", "Pages inactive", "Pages speculative")):
                    available_pages += int(line.split(":")[1].strip().strip("."))
            if available_pages:
                return (available_pages * page_size) / (1024**3)
        except (ValueError, IndexError):
            return None
        return None
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_AVPHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return (pages * page_size) / (1024**3)
        except (ValueError, OSError, AttributeError):
            return None
    return None


def stage_record(name: str, start: float, end: float, files: int = 0, candidates: int = 0, outputs: list[Path] | None = None) -> dict[str, Any]:
    return {
        "stage": name,
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start)),
        "end_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end)),
        "elapsed_seconds": round(end - start, 3),
        "files_processed": files,
        "candidate_segments_processed": candidates,
        "outputs_created": "; ".join(str(path) for path in (outputs or []) if path.exists()),
    }


def diagnose_bottleneck(slowest_stage: str) -> str:
    stage = slowest_stage.lower()
    if "rendering" in stage or "export" in stage or "assembling" in stage or "music" in stage:
        if "assembling" in stage:
            return "Most time was spent assembling the rough cut. Try fewer clips or simpler hard-cut transitions."
        return "Most time was spent rendering/exporting, so ffmpeg encoding is probably the bottleneck. Try lower export resolution, Fast Preview mode, or shorter clips."
    if "analyzing" in stage:
        return "Most time was spent analyzing frames, so Python/OpenCV frame analysis is probably the bottleneck. Try Fast Preview mode and reuse the analysis cache."
    if "thumbnail" in stage:
        return "Most time was spent generating thumbnails, so preview extraction and disk cache work are probably the bottleneck."
    if "metadata" in stage or "scanning" in stage:
        return "Most time was spent scanning/probing files, so disk I/O or ffprobe metadata reads are probably the bottleneck."
    if "scoring" in stage or "selecting" in stage:
        return "Most time was spent scoring/selecting segments, so candidate volume and comparison work are probably the bottleneck."
    return "No single obvious bottleneck was identified."


def write_performance_report(stages: list[dict[str, Any]], config: dict[str, Any], deps: DependencyInfo, selected_files: list[Path], total_candidates: int) -> None:
    total_elapsed = sum(float(stage["elapsed_seconds"]) for stage in stages)
    slowest = max(stages, key=lambda item: float(item["elapsed_seconds"])) if stages else None
    for stage in stages:
        stage["percent_of_total"] = round((float(stage["elapsed_seconds"]) / total_elapsed) * 100, 1) if total_elapsed > 0 else 0.0

    with PERFORMANCE_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "stage",
            "start_time",
            "end_time",
            "elapsed_seconds",
            "percent_of_total",
            "files_processed",
            "candidate_segments_processed",
            "outputs_created",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for stage in stages:
            writer.writerow({key: stage.get(key, "") for key in fieldnames})

    ffmpeg_version = command_output([deps.ffmpeg, "-version"]).splitlines()[0] if deps.ffmpeg else "not found"
    memory = available_memory_gb()
    total_size = sum(path.stat().st_size for path in selected_files if path.exists()) / (1024 * 1024)
    diagnosis = diagnose_bottleneck(str(slowest["stage"])) if slowest else "No stages were recorded."

    lines = [
        "Performance Summary",
        "===================",
        f"Total elapsed time: {total_elapsed:.2f} seconds",
        f"Slowest stage: {slowest['stage']} ({slowest['elapsed_seconds']}s, {slowest['percent_of_total']}%)" if slowest else "Slowest stage: unknown",
        f"Bottleneck diagnosis: {diagnosis}",
        "",
        "Stage Timings",
        "-------------",
    ]
    for stage in stages:
        lines.append(f"- {stage['stage']}: {stage['elapsed_seconds']}s ({stage['percent_of_total']}%), files={stage['files_processed']}, candidates={stage['candidate_segments_processed']}")
    lines.extend(
        [
            "",
            "System Snapshot",
            "---------------",
            f"Python version: {sys.version.split()[0]}",
            f"ffmpeg path: {deps.ffmpeg or 'not found'}",
            f"ffprobe path: {deps.ffprobe or 'not found'}",
            f"ffmpeg version: {ffmpeg_version}",
            f"CPU count: {os.cpu_count() or 'unknown'}",
            f"Available memory: {memory:.1f} GB" if memory is not None else "Available memory: unknown",
            f"Source footage count: {len(selected_files)}",
            f"Total source footage size: {total_size:.1f} MB",
            f"Total candidate segments: {total_candidates}",
            f"Output resolution: {config.get('resolution')} {config.get('aspect_ratio')}",
            f"Render mode: {config.get('render_mode', 'Final Quality')}",
            f"Transition style: {config.get('transition_style')}",
            f"Target duration: {config.get('target_duration')} seconds",
            f"Number of shots: {config.get('number_of_shots')}",
            f"Music mode: {config.get('music_mode')}",
        ]
    )
    PERFORMANCE_TXT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze_clip(info: ClipInfo, clip_length: float, render_mode: str = "Final Quality") -> list[Candidate]:
    cap = cv2.VideoCapture(str(info.path))
    if not cap.isOpened():
        return []
    sample_step = max(2.0, min(4.0, clip_length)) if render_mode == "Fast Preview" else max(1.0, min(2.0, clip_length / 2))
    times = np.arange(0, max(info.duration - 0.25, 0), sample_step)
    samples: list[dict[str, Any]] = []
    previous = None
    for time_s in times:
        frame = read_frame(cap, float(time_s), info.fps)
        if frame is None:
            continue
        if render_mode == "Fast Preview" and frame.shape[1] > 960:
            scale = 960 / frame.shape[1]
            frame = cv2.resize(frame, (960, int(frame.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        motion = motion_score(previous, frame)
        samples.append({"time": float(time_s), "motion": motion, "sharpness": sharpness_score(frame), "hist": frame_hist(frame)})
        previous = frame
    cap.release()
    if len(samples) < 2:
        return []

    candidates: list[Candidate] = []
    start_stride = max(clip_length, 2.0) if render_mode == "Fast Preview" else max(clip_length / 2, 1.0)
    starts = np.arange(0, max(info.duration - clip_length, 0) + 0.01, start_stride)
    for start in starts:
        end = min(float(start) + clip_length, info.duration)
        window = [sample for sample in samples if start <= float(sample["time"]) <= end]
        if len(window) < 2:
            continue
        motions = [float(sample["motion"]) for sample in window]
        sharpnesses = [float(sample["sharpness"]) for sample in window]
        hists = [sample["hist"] for sample in window]
        hist = np.mean(np.stack(hists), axis=0).astype(np.float32)
        motion_std = float(np.std(motions))
        variety = float(np.mean([cv2.compareHist(hists[0], item, cv2.HISTCMP_BHATTACHARYYA) for item in hists[1:]]))
        candidates.append(
            Candidate(
                source=info.path,
                start=float(start),
                end=float(end),
                duration=float(end - start),
                score=0.0,
                motion=float(np.mean(motions)),
                sharpness=float(np.mean(sharpnesses)),
                stability=1.0 / (1.0 + motion_std),
                variety=variety,
                thumb_time=float(start + ((end - start) / 2)),
                hist=hist,
            )
        )
    return candidates


def analysis_cache_path(info: ClipInfo, clip_length: float, render_mode: str, look_for_subjects: bool) -> Path:
    key = f"{info.path.resolve()}|{info.path.stat().st_size}|{info.path.stat().st_mtime_ns}|{info.duration:.3f}|{clip_length:.2f}|{render_mode}|{look_for_subjects}"
    return ANALYSIS_CACHE_DIR / f"{hashlib.sha1(key.encode('utf-8')).hexdigest()}.json"


def candidate_to_cache(item: Candidate) -> dict[str, Any]:
    return {
        "source": str(item.source),
        "start": item.start,
        "end": item.end,
        "duration": item.duration,
        "score": item.score,
        "motion": item.motion,
        "sharpness": item.sharpness,
        "stability": item.stability,
        "variety": item.variety,
        "thumb_time": item.thumb_time,
        "hist": item.hist.tolist(),
        "reason": item.reason,
        "subject_hint": item.subject_hint,
        "subject_x": item.subject_x,
        "subject_y": item.subject_y,
    }


def candidate_from_cache(data: dict[str, Any]) -> Candidate:
    return Candidate(
        source=Path(data["source"]),
        start=float(data["start"]),
        end=float(data["end"]),
        duration=float(data["duration"]),
        score=float(data.get("score", 0.0)),
        motion=float(data.get("motion", 0.0)),
        sharpness=float(data.get("sharpness", 0.0)),
        stability=float(data.get("stability", 0.0)),
        variety=float(data.get("variety", 0.0)),
        thumb_time=float(data.get("thumb_time", data.get("start", 0.0))),
        hist=np.array(data.get("hist", []), dtype=np.float32),
        reason=str(data.get("reason", "")),
        subject_hint=bool(data.get("subject_hint", False)),
        subject_x=float(data.get("subject_x", 0.5)),
        subject_y=float(data.get("subject_y", 0.5)),
    )


def detect_small_subject_hint(info: ClipInfo, start: float, end: float) -> tuple[bool, float, float]:
    cap = cv2.VideoCapture(str(info.path))
    if not cap.isOpened():
        return False, 0.5, 0.5
    fps = info.fps or 30
    times = np.linspace(start, end, num=4)
    previous = None
    best_area = 0
    best_center = (0.5, 0.5)
    for time_s in times:
        frame = read_frame(cap, float(time_s), fps)
        if frame is None:
            continue
        small = cv2.resize(frame, (240, 135), interpolation=cv2.INTER_AREA)
        gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        if previous is not None:
            diff = cv2.absdiff(previous, gray)
            _, thresh = cv2.threshold(diff, 24, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = cv2.contourArea(contour)
                if 8 <= area <= 350 and area > best_area:
                    x, y, w, h = cv2.boundingRect(contour)
                    best_area = area
                    best_center = ((x + w / 2) / 240, (y + h / 2) / 135)
        previous = gray
    cap.release()
    return best_area > 0, float(best_center[0]), float(best_center[1])


def analyze_clip_cached(info: ClipInfo, clip_length: float, render_mode: str, look_for_subjects: bool) -> tuple[list[Candidate], bool, float]:
    cache_path = analysis_cache_path(info, clip_length, render_mode, look_for_subjects)
    if cache_path.exists():
        try:
            started = time.time()
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return [candidate_from_cache(item) for item in payload.get("candidates", [])], True, max(0.0, float(payload.get("analysis_seconds", 0.0)) - (time.time() - started))
        except Exception:
            cache_path.unlink(missing_ok=True)
    started = time.time()
    candidates = analyze_clip(info, clip_length, render_mode)
    if look_for_subjects:
        for item in candidates:
            hint, x, y = detect_small_subject_hint(info, item.start, item.end)
            item.subject_hint = hint
            item.subject_x = x
            item.subject_y = y
    elapsed = time.time() - started
    cache_path.write_text(json.dumps({"analysis_seconds": elapsed, "candidates": [candidate_to_cache(item) for item in candidates]}, indent=2), encoding="utf-8")
    return candidates, False, 0.0


def score_candidates(candidates: list[Candidate], motion_preference: str) -> list[Candidate]:
    motion_norm = normalize([item.motion for item in candidates])
    sharp_norm = normalize([item.sharpness for item in candidates])
    stability_norm = normalize([item.stability for item in candidates])
    variety_norm = normalize([item.variety for item in candidates])
    for idx, item in enumerate(candidates):
        motion_value = motion_norm[idx]
        if motion_preference == "low":
            motion_component = 1 - motion_value
        elif motion_preference == "high":
            motion_component = motion_value
        else:
            motion_component = 1 - abs(motion_value - 0.55)
        item.score = 0.34 * sharp_norm[idx] + 0.30 * motion_component + 0.18 * stability_norm[idx] + 0.18 * variety_norm[idx]
        if item.subject_hint:
            item.score = min(1.0, item.score + 0.06)
    return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)


def discovery_reason(item: Candidate) -> str:
    reasons = []
    if item.stability > 0.55 and item.motion > 6:
        reasons.append("smooth forward motion with strong visual change")
    if item.sharpness > 120:
        reasons.append("sharp landscape detail")
    if item.motion > 12 and item.stability < 0.45:
        reasons.append("high motion but slightly unstable")
    if item.variety > 0.20:
        reasons.append("visually distinct from other selected clips")
    if item.subject_hint:
        reasons.append("possible small moving subject detected")
    return "; ".join(reasons) or "balanced motion, sharpness, stability, and novelty"


def discovery_rows(candidates: list[Candidate], limit: int = 120) -> list[dict[str, Any]]:
    ranked = sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]
    rows = []
    for rank, item in enumerate(ranked, start=1):
        rows.append(
            {
                "label": "Maybe",
                "rank": rank,
                "thumbnail": discovery_thumbnail_uri(item, rank),
                "source_filename": item.source.name,
                "source_path": str(item.source),
                "start_time": round(item.start, 2),
                "end_time": round(item.end, 2),
                "duration": round(item.duration, 2),
                "motion_score": round(item.motion, 3),
                "sharpness_score": round(item.sharpness, 3),
                "stability_score": round(item.stability, 3),
                "novelty_score": round(item.variety, 3),
                "interestingness_score": round(item.score, 3),
                "reason": discovery_reason(item),
                "subject_x": round(item.subject_x, 3),
                "subject_y": round(item.subject_y, 3),
            }
        )
    return rows


def discovery_thumbnail_uri(item: Candidate, rank: int) -> str:
    cached = THUMBNAIL_DIR / f"discovery_{hashlib.sha1(f'{item.source}|{item.start:.2f}|{item.end:.2f}'.encode('utf-8')).hexdigest()}.jpg"
    if cached.exists():
        return image_data_uri(cached)
    cap = cv2.VideoCapture(str(item.source))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame = read_frame(cap, item.thumb_time, fps)
    cap.release()
    if frame is None:
        return placeholder_thumbnail()
    thumb = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(cached), thumb)
    return image_data_uri(cached)


def save_clip_review(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = ["label", "rank", "source_filename", "source_path", "start_time", "end_time", "duration", "motion_score", "sharpness_score", "stability_score", "novelty_score", "interestingness_score", "reason", "subject_x", "subject_y"]
    with (OUTPUT_DIR / "clip_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def load_clip_review() -> list[dict[str, Any]]:
    path = OUTPUT_DIR / "clip_review.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def safe_slug(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return "_".join(part for part in clean.split("_") if part)[:80] or "clip"


def export_review_clips(rows: list[dict[str, Any]], ffmpeg: str, subject_focus: bool = False) -> list[dict[str, Any]]:
    output_dir = SUBJECT_FOCUS_DIR if subject_focus else MUST_REVIEW_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    for row in rows:
        label = str(row.get("label", ""))
        if subject_focus:
            include = label == "Possible animal/bird"
        else:
            include = label == "Must review"
        if not include:
            continue
        source = Path(str(row["source_path"]))
        start = float(row["start_time"])
        end = float(row["end_time"])
        duration = max(0.1, end - start)
        reason = safe_slug(str(row.get("reason", "review"))[:40])
        output = output_dir / f"{safe_slug(source.stem)}_{start:.1f}_{end:.1f}_{reason}.mp4"
        command = [ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source)]
        if subject_focus:
            x = float(row.get("subject_x") or 0.5)
            y = float(row.get("subject_y") or 0.5)
            crop = f"crop=iw*0.55:ih*0.55:clip(iw*{x:.3f}-iw*0.275\\,0\\,iw*0.45):clip(ih*{y:.3f}-ih*0.275\\,0\\,ih*0.45),scale=iw*1.4:ih*1.4,setpts=1.15*PTS"
            command += ["-vf", crop]
        command += ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(output)]
        run_command(command)
        exported_row = dict(row)
        exported_row["exported_clip_path"] = str(output)
        exported.append(exported_row)
    return exported


def save_davinci_review_list(rows: list[dict[str, Any]]) -> None:
    fieldnames = ["source file", "start time", "end time", "label", "reason", "score", "exported clip path"]
    with (OUTPUT_DIR / "davinci_review_list.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "source file": row.get("source_path", ""),
                    "start time": row.get("start_time", ""),
                    "end time": row.get("end_time", ""),
                    "label": row.get("label", ""),
                    "reason": row.get("reason", ""),
                    "score": row.get("interestingness_score", ""),
                    "exported clip path": row.get("exported_clip_path", ""),
                }
            )


def too_similar(candidate: Candidate, selected: list[Candidate], threshold: float) -> bool:
    return any(cv2.compareHist(candidate.hist, item.hist, cv2.HISTCMP_CORREL) >= threshold for item in selected)


def overlaps_existing(candidate: Candidate, selected: list[Candidate]) -> bool:
    return any(candidate.source == item.source and candidate.start < item.end and item.start < candidate.end for item in selected)


def select_segments(
    candidates: list[Candidate],
    number_of_shots: int,
    blur_rejection: str,
    similarity_rejection: str,
    min_per_video: int,
    max_per_video: int,
    selected_sources: list[Path],
) -> tuple[list[Candidate], list[Candidate]]:
    if not candidates:
        return [], []
    blur_percentile = {"low": 5, "medium": 20, "high": 35}[blur_rejection]
    similarity_cutoff = {"low": 0.96, "medium": 0.90, "high": 0.84}[similarity_rejection]
    sharp_cutoff = float(np.percentile([item.sharpness for item in candidates], blur_percentile))
    selected: list[Candidate] = []
    rejected: list[Candidate] = []
    counts: dict[Path, int] = {}

    if min_per_video == 1:
        for source in selected_sources:
            best = next((item for item in candidates if item.source == source and item.sharpness >= sharp_cutoff), None)
            if best and len(selected) < number_of_shots:
                best.reason = "best available segment from selected source"
                selected.append(best)
                counts[source] = counts.get(source, 0) + 1

    for item in candidates:
        if len(selected) >= number_of_shots:
            break
        if item in selected:
            continue
        if counts.get(item.source, 0) >= max_per_video:
            item.rejection_reason = "maximum clips from source reached"
            rejected.append(item)
            continue
        if item.sharpness < sharp_cutoff:
            item.rejection_reason = "below blur rejection sharpness threshold"
            rejected.append(item)
            continue
        if overlaps_existing(item, selected):
            item.rejection_reason = "overlaps a stronger selected segment"
            rejected.append(item)
            continue
        if too_similar(item, selected, similarity_cutoff):
            item.rejection_reason = "too visually similar to selected segment"
            rejected.append(item)
            continue
        item.reason = "global score: motion/change, sharpness, stability, and visual variety"
        selected.append(item)
        counts[item.source] = counts.get(item.source, 0) + 1

    if len(selected) < number_of_shots:
        for item in candidates:
            if len(selected) >= number_of_shots:
                break
            if item in selected or overlaps_existing(item, selected) or counts.get(item.source, 0) >= max_per_video:
                continue
            item.reason = "fallback high global score"
            selected.append(item)
            counts[item.source] = counts.get(item.source, 0) + 1

    selected_set = set(id(item) for item in selected)
    for item in candidates:
        if id(item) not in selected_set and not item.rejection_reason:
            item.rejection_reason = "not in top selected global segments"
            rejected.append(item)
    return sorted(selected, key=lambda item: (item.source.name, item.start)), rejected[:100]


def preset_values(name: str) -> dict[str, float]:
    return {
        "Natural Documentary": {"exposure": 0.0, "contrast": 1.05, "saturation": 1.05, "temperature": 0.0, "sharpness": 0.25},
        "Moody Alpine": {"exposure": -0.03, "contrast": 1.18, "saturation": 0.88, "temperature": -0.10, "sharpness": 0.35},
        "Warm Travel": {"exposure": 0.02, "contrast": 1.08, "saturation": 1.18, "temperature": 0.14, "sharpness": 0.20},
        "High-Contrast Adventure": {"exposure": 0.0, "contrast": 1.28, "saturation": 1.12, "temperature": 0.02, "sharpness": 0.45},
    }[name]


def output_size(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    if resolution == "720p":
        return (1280, 720) if aspect_ratio == "16:9" else (720, 1280)
    if aspect_ratio == "16:9":
        return (3840, 2160) if resolution == "4K" else (1920, 1080)
    return (2160, 3840) if resolution == "4K" else (1080, 1920)


def effective_resolution(render_mode: str, resolution: str) -> str:
    return "720p" if render_mode == "Fast Preview" else resolution


def output_video_path(render_mode: str) -> Path:
    return OUTPUT_DIR / ("rough_cut_preview.mp4" if render_mode == "Fast Preview" else "rough_cut.mp4")


def video_filter(aspect_ratio: str, resolution: str, controls: dict[str, float]) -> str:
    width, height = output_size(aspect_ratio, resolution)
    temp = float(np.clip(controls["temperature"], -0.25, 0.25))
    filters = [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
        f"eq=brightness={controls['exposure']:.3f}:contrast={controls['contrast']:.3f}:saturation={controls['saturation']:.3f}",
        f"colorbalance=rs={temp:.3f}:bs={-temp:.3f}",
    ]
    if controls["sharpness"] > 0:
        filters.append(f"unsharp=5:5:{0.4 + controls['sharpness'] * 1.2:.2f}:5:5:0.0")
    return ",".join(filters)


def make_selected_clips(selected: list[Candidate], aspect_ratio: str, resolution: str, controls: dict[str, float], ffmpeg: str) -> list[Path]:
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)
    for path in SELECTED_DIR.glob("*.mp4"):
        path.unlink(missing_ok=True)
    rendered: list[Path] = []
    filter_chain = video_filter(aspect_ratio, resolution, controls)
    for idx, item in enumerate(selected, start=1):
        append_log(f"Rendering clip {idx}/{len(selected)} from {item.source.name}")
        output = SELECTED_DIR / f"{idx:02d}_{item.source.stem}.mp4"
        run_command(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{item.start:.3f}",
                "-t",
                f"{item.duration:.3f}",
                "-i",
                str(item.source),
                "-an",
                "-vf",
                filter_chain,
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(output),
            ]
        )
        rendered.append(output)
    return rendered


def assemble_silent(rendered: list[Path], transition_style: str, ffmpeg: str, ffprobe: str | None) -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    output = TEMP_DIR / "rough_cut_silent.mp4"
    if transition_style == "hard cuts" or len(rendered) == 1:
        list_file = OUTPUT_DIR / "concat_list.txt"
        list_file.write_text("".join(f"file '{path.as_posix()}'\n" for path in rendered), encoding="utf-8")
        run_command([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-an", "-c:v", "copy", str(output)])
        return output

    durations = [probe_duration(path, ffprobe) or (inspect_clip(path).duration if inspect_clip(path) else 0) for path in rendered]
    if any(duration <= 0 for duration in durations):
        raise RuntimeError("Could not read rendered clip durations for crossfades.")
    inputs: list[str] = []
    for path in rendered:
        inputs.extend(["-i", str(path)])
    fade_duration = 0.35
    current_label = "0:v"
    running_duration = durations[0]
    filters = []
    for idx in range(1, len(rendered)):
        next_label = f"v{idx}"
        filters.append(f"[{current_label}][{idx}:v]xfade=transition=fade:duration={fade_duration:.2f}:offset={max(0.05, running_duration - fade_duration):.3f}[{next_label}]")
        current_label = next_label
        running_duration += durations[idx] - fade_duration
    run_command([ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", f"[{current_label}]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(output)])
    return output


def add_music_or_finalize(silent_video: Path, music: Path | None, final_duration: float, ffmpeg: str, output: Path) -> Path:
    if not music:
        append_log("Exporting without music")
        shutil.move(str(silent_video), str(output))
        return output
    append_log(f"Adding music: {music.name}")
    fade_out_start = max(0.0, final_duration - 2.0)
    run_command(
        [
            ffmpeg,
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(music),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            f"{final_duration:.3f}",
            "-af",
            f"afade=t=in:st=0:d=1,afade=t=out:st={fade_out_start:.3f}:d=2",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ]
    )
    silent_video.unlink(missing_ok=True)
    return output


def save_edit_decisions(selected: list[Candidate]) -> None:
    with (OUTPUT_DIR / "edit_decisions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_filename", "start_time", "end_time", "duration", "motion_score", "sharpness_score", "variety_score", "total_score", "reason_selected"])
        for item in selected:
            writer.writerow([item.source.name, f"{item.start:.2f}", f"{item.end:.2f}", f"{item.duration:.2f}", f"{item.motion:.3f}", f"{item.sharpness:.3f}", f"{item.variety:.3f}", f"{item.score:.3f}", item.reason])


def save_rejected_segments(rejected: list[Candidate]) -> None:
    with (OUTPUT_DIR / "rejected_segments.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_filename", "start_time", "end_time", "duration", "total_score", "reason_rejected"])
        for item in rejected:
            writer.writerow([item.source.name, f"{item.start:.2f}", f"{item.end:.2f}", f"{item.duration:.2f}", f"{item.score:.3f}", item.rejection_reason])


def save_contact_sheet(selected: list[Candidate]) -> None:
    thumbs: list[np.ndarray] = []
    for item in selected:
        cap = cv2.VideoCapture(str(item.source))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame = read_frame(cap, item.thumb_time, fps)
        cap.release()
        if frame is None:
            continue
        thumb = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
        label = f"{item.source.name}  {item.start:.1f}s"
        cv2.rectangle(thumb, (0, 148), (320, 180), (0, 0, 0), -1)
        cv2.putText(thumb, label[:42], (8, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        thumbs.append(thumb)
    if not thumbs:
        return
    columns = min(4, len(thumbs))
    rows = math.ceil(len(thumbs) / columns)
    sheet = np.full((rows * 180, columns * 320, 3), 24, dtype=np.uint8)
    for idx, thumb in enumerate(thumbs):
        row = idx // columns
        column = idx % columns
        sheet[row * 180 : (row + 1) * 180, column * 320 : (column + 1) * 320] = thumb
    cv2.imwrite(str(OUTPUT_DIR / "contact_sheet.jpg"), sheet)


def load_music_library() -> list[dict[str, str]]:
    tracks = music_library_tracks()
    by_name = {track.name: track for track in tracks}
    by_rel = {str(track.relative_to(MUSIC_LIBRARY_DIR)): track for track in tracks if track.is_relative_to(MUSIC_LIBRARY_DIR)}
    csv_path = MUSIC_LIBRARY_DIR / "music_library.csv"
    rows: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                filename = row.get("filename", "")
                track = by_rel.get(filename) or by_name.get(filename)
                if track:
                    row["path"] = str(track)
                    rows.append(row)
    known = {row.get("filename") for row in rows}
    for track in tracks:
        if track.name not in known:
            rows.append({"filename": track.name, "title": track.stem, "artist": "", "mood": "", "bpm": "", "license": "", "source_url": "", "attribution_required": "false", "attribution_text": "", "path": str(track)})
    return rows


def choose_library_music(mood: str, target_duration: int, ffprobe: str | None) -> dict[str, str] | None:
    rows = load_music_library()
    matching = [row for row in rows if row.get("mood", "").strip().lower() == mood]
    candidates = matching or rows
    long_enough = []
    for row in candidates:
        duration = probe_duration(Path(row["path"]), ffprobe) or 0
        if duration >= target_duration:
            row["duration"] = f"{duration:.2f}"
            long_enough.append(row)
    if long_enough:
        return random.choice(long_enough)
    fallback = []
    for row in rows:
        duration = probe_duration(Path(row["path"]), ffprobe) or 0
        if duration >= target_duration:
            row["duration"] = f"{duration:.2f}"
            fallback.append(row)
    return random.choice(fallback) if fallback else None


def describe_music_row(row: dict[str, str] | None) -> str:
    if not row:
        return "None"
    title = row.get("title") or Path(row.get("path", row.get("filename", ""))).stem
    artist = row.get("artist")
    filename = row.get("filename", "")
    return f"{title} - {artist} ({filename})" if artist else f"{title} ({filename})"


def save_music_used(music_row: dict[str, str] | None, music_path: Path | None, mode: str) -> None:
    with (OUTPUT_DIR / "music_used.txt").open("w", encoding="utf-8") as handle:
        handle.write(f"Music mode: {mode}\n")
        if not music_path:
            handle.write("No music used.\n")
            return
        handle.write(f"File: {music_path}\n")
        if music_row:
            for key in ["title", "artist", "mood", "bpm", "license", "source_url"]:
                if music_row.get(key):
                    handle.write(f"{key}: {music_row[key]}\n")
            if music_row.get("attribution_required", "").strip().lower() in {"true", "yes", "1"}:
                handle.write("Attribution required: yes\n")
                handle.write(f"Attribution text: {music_row.get('attribution_text', '')}\n")


def run_worker(config_path: Path) -> None:
    ensure_dirs()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    RUN_LOG_PATH.write_text("", encoding="utf-8")
    started = time.time()
    deps = detect_dependencies()
    stage_timings: list[dict[str, Any]] = []
    selected_files: list[Path] = []
    candidates: list[Candidate] = []
    try:
        clean_partial_outputs()
        write_status("Scanning videos", 4, started_at=started)
        append_log("Starting rough-cut job")
        stage_start = time.time()
        selected_files = [Path(path) for path in config["selected_files"]]
        stage_end = time.time()
        stage_timings.append(stage_record("scanning files", stage_start, stage_end, files=len(selected_files)))

        write_status("Scanning videos", 12, started_at=started)
        stage_start = time.time()
        infos = [info for path in selected_files if (info := inspect_clip(path, deps.ffprobe))]
        stage_end = time.time()
        stage_timings.append(stage_record("extracting metadata", stage_start, stage_end, files=len(selected_files)))
        append_log(f"Loaded metadata for {len(infos)} selected videos")
        if not infos:
            raise RuntimeError("No selected videos could be read.")

        render_mode = config.get("render_mode", "Final Quality")
        look_for_subjects = bool(config.get("look_for_subjects", False))
        write_status("Generating thumbnails", 16, started_at=started)
        stage_start = time.time()
        for info in infos:
            generate_video_thumbnail(info.path, info)
        stage_end = time.time()
        stage_timings.append(stage_record("generating thumbnails", stage_start, stage_end, files=len(infos), outputs=list(THUMBNAIL_DIR.glob("*.jpg"))[:20]))

        clip_length = float(np.clip(config["target_duration"] / config["number_of_shots"], config["min_clip_length"], config["max_clip_length"]))
        if render_mode == "Fast Preview":
            clip_length = max(clip_length, 3.0)
        stage_start = time.time()
        fresh_count = 0
        cached_count = 0
        estimated_saved = 0.0
        for idx, info in enumerate(infos, start=1):
            write_status("Analyzing frames", 15 + int(25 * idx / max(1, len(infos))), started_at=started, message=info.path.name)
            analyzed, from_cache, saved = analyze_clip_cached(info, clip_length, render_mode, look_for_subjects)
            if from_cache:
                cached_count += 1
                estimated_saved += saved
                append_log(f"Loaded analysis cache for {info.path.name}")
            else:
                fresh_count += 1
                append_log(f"Analyzed fresh: {info.path.name}")
            candidates.extend(analyzed)
        stage_end = time.time()
        stage_timings.append(stage_record("analyzing frames", stage_start, stage_end, files=len(infos), candidates=len(candidates)))
        append_log(f"Analysis cache: {fresh_count} fresh, {cached_count} cached, estimated time saved {estimated_saved:.1f}s")
        if not candidates:
            raise RuntimeError("No candidate segments were found.")

        write_status("Scoring candidate segments", 45, started_at=started)
        stage_start = time.time()
        candidates = score_candidates(candidates, config["motion_preference"])
        stage_end = time.time()
        stage_timings.append(stage_record("scoring candidate segments", stage_start, stage_end, candidates=len(candidates)))
        append_log(f"Scored {len(candidates)} candidate segments globally")

        write_status("Selecting final clips", 55, started_at=started)
        stage_start = time.time()
        selected, rejected = select_segments(candidates, config["number_of_shots"], config["blur_rejection"], config["similarity_rejection"], config["min_per_video"], config["max_per_video"], selected_files)
        if not selected:
            raise RuntimeError("No segments survived selection. Try lower rejection settings.")
        append_log(f"Selected {len(selected)} final clips")
        save_edit_decisions(selected)
        save_rejected_segments(rejected)
        save_contact_sheet(selected)
        stage_end = time.time()
        stage_timings.append(
            stage_record(
                "selecting final clips",
                stage_start,
                stage_end,
                candidates=len(candidates),
                outputs=[OUTPUT_DIR / "edit_decisions.csv", OUTPUT_DIR / "rejected_segments.csv", OUTPUT_DIR / "contact_sheet.jpg"],
            )
        )

        music_path: Path | None = None
        music_row: dict[str, str] | None = None
        if config["music_mode"] == "Use my own music file":
            candidate = Path(config["music_file"]).expanduser()
            if is_valid_audio_file(candidate):
                music_path = candidate
                append_log(f"Using own music file: {music_path.name}")
            else:
                raise RuntimeError("Selected music file does not exist or is not .mp3, .wav, .m4a, .flac, or .ogg.")
        elif config["music_mode"] == "Auto-select music":
            music_row = choose_library_music(config["music_mood"], config["target_duration"], deps.ffprobe)
            if music_row:
                music_path = Path(music_row["path"])
                append_log(f"Auto-selected music: {describe_music_row(music_row)}")
            elif config.get("continue_without_music"):
                append_log("No matching auto-selected music found. Continuing without music by user choice.")
            else:
                raise RuntimeError("No matching music found. Add tracks to ./music_library/ or choose Continue without music.")
        save_music_used(music_row, music_path, config["music_mode"])

        if not deps.ffmpeg:
            append_log("ffmpeg is missing. Analysis outputs were created; video export skipped.")
            write_performance_report(stage_timings, config, deps, selected_files, len(candidates))
            write_status("Done", 100, status="done", message="Analysis complete. ffmpeg missing, so video export was skipped.", started_at=started)
            return

        write_status("Rendering clips", 65, started_at=started)
        stage_start = time.time()
        export_resolution = effective_resolution(render_mode, config["resolution"])
        rendered = make_selected_clips(selected, config["aspect_ratio"], export_resolution, config["controls"], deps.ffmpeg)
        stage_end = time.time()
        stage_timings.append(stage_record("rendering selected clips", stage_start, stage_end, files=len(rendered), outputs=rendered))
        write_status("Assembling rough cut", 82, started_at=started)
        stage_start = time.time()
        silent = assemble_silent(rendered, config["transition_style"], deps.ffmpeg, deps.ffprobe)
        stage_end = time.time()
        stage_timings.append(stage_record("assembling rough cut", stage_start, stage_end, files=len(rendered), outputs=[silent]))
        write_status("Exporting final video", 90, started_at=started)
        final_duration = sum(item.duration for item in selected)
        status_message_path = Path(str(status.get("message", ""))) if status.get("message") else None
        final_output = status_message_path if status_message_path and status_message_path.exists() else output_video_path(render_mode)
        if music_path:
            stage_start = time.time()
            final = add_music_or_finalize(silent, music_path, final_duration, deps.ffmpeg, final_output)
            stage_end = time.time()
            stage_timings.append(stage_record("adding music", stage_start, stage_end, files=1, outputs=[final]))
            stage_start = time.time()
            final.exists()
            stage_end = time.time()
            stage_timings.append(stage_record("final export", stage_start, stage_end, outputs=[final]))
        else:
            stage_start = time.time()
            stage_end = time.time()
            stage_timings.append(stage_record("adding music", stage_start, stage_end, files=0))
            stage_start = time.time()
            final = add_music_or_finalize(silent, music_path, final_duration, deps.ffmpeg, final_output)
            stage_end = time.time()
            stage_timings.append(stage_record("final export", stage_start, stage_end, outputs=[final]))
        append_log(f"Exported {final}")
        write_performance_report(stage_timings, config, deps, selected_files, len(candidates))
        write_status("Done", 100, status="done", message=str(final), started_at=started)
    except KeyboardInterrupt:
        append_log("Cancelled by user")
        write_performance_report(stage_timings, config, deps, selected_files, len(candidates))
        write_status("Done", 100, status="cancelled", message="Cancelled by user", started_at=started)
    except Exception as exc:
        append_log(f"Failed: {exc}")
        if stage_timings:
            write_performance_report(stage_timings, config, deps, selected_files, len(candidates))
        write_status("Done", 100, status="failed", message=str(exc), started_at=started)
        raise


def readable_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = int(seconds % 60)
    return f"{minutes}:{remaining:02d}"


def file_rows(clips: list[Path], ffprobe: str | None) -> list[dict[str, Any]]:
    rows = []
    for idx, path in enumerate(clips):
        info = inspect_clip(path, ffprobe)
        rows.append(
            {
                "include": False,
                "thumbnail": generate_video_thumbnail(path, info),
                "filename": path.name,
                "duration": readable_duration(info.duration) if info else "unknown",
                "duration_seconds": float(info.duration) if info else 0.0,
                "resolution": f"{info.width}x{info.height}" if info else "unknown",
                "file_size_mb": round(info.size_mb, 1) if info else round(path.stat().st_size / (1024 * 1024), 1),
                "modified": path.stat().st_mtime,
                "path": str(path),
            }
        )
    return rows


def load_edit_decisions() -> list[dict[str, Any]]:
    path = OUTPUT_DIR / "edit_decisions.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for idx, row in enumerate(rows, start=1):
        row["clip_number"] = idx
        source = row.get("source_filename", "")
        start = row.get("start_time", "")
        row["thumbnail"] = segment_thumbnail_uri(source, start, idx)
    return rows


def load_performance_rows() -> list[dict[str, Any]]:
    if not PERFORMANCE_CSV_PATH.exists():
        return []
    with PERFORMANCE_CSV_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def performance_diagnosis_text() -> str:
    if not PERFORMANCE_TXT_PATH.exists():
        return ""
    text = PERFORMANCE_TXT_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("Bottleneck diagnosis:"):
            return line.replace("Bottleneck diagnosis:", "").strip()
    return ""


def show_performance_summary() -> None:
    performance_rows = load_performance_rows()
    if not performance_rows:
        return
    st.markdown("**Performance Summary**")
    slowest = max(performance_rows, key=lambda row: float(row.get("elapsed_seconds") or 0))
    perf_cols = st.columns(3)
    perf_cols[0].metric("Slowest stage", slowest.get("stage", "unknown"))
    perf_cols[1].metric("Slowest stage time", f"{float(slowest.get('elapsed_seconds') or 0):.1f}s")
    perf_cols[2].metric("Share of total", f"{float(slowest.get('percent_of_total') or 0):.1f}%")
    diagnosis = performance_diagnosis_text()
    if diagnosis:
        st.info(diagnosis)
    st.dataframe(performance_rows, hide_index=True, use_container_width=True)
    st.caption(f"Reports: `{PERFORMANCE_CSV_PATH}` and `{PERFORMANCE_TXT_PATH}`")


def segment_thumbnail_uri(source_filename: str, start_time: str, clip_number: int) -> str:
    contact_sheet = OUTPUT_DIR / "contact_sheet.jpg"
    if not contact_sheet.exists():
        return placeholder_thumbnail()
    cached = THUMBNAIL_DIR / f"selected_{clip_number:02d}.jpg"
    if cached.exists():
        return image_data_uri(cached)
    try:
        sheet = cv2.imread(str(contact_sheet))
        if sheet is None:
            return placeholder_thumbnail()
        columns = min(4, max(1, math.ceil(math.sqrt(max(clip_number, 1)))))
        columns = 4 if sheet.shape[1] >= 1280 else max(1, sheet.shape[1] // 320)
        idx = clip_number - 1
        row = idx // columns
        column = idx % columns
        tile = sheet[row * 180 : (row + 1) * 180, column * 320 : (column + 1) * 320]
        if tile.size == 0:
            return placeholder_thumbnail()
        cv2.imwrite(str(cached), cv2.resize(tile, (160, 90), interpolation=cv2.INTER_AREA))
        return image_data_uri(cached)
    except Exception:
        return placeholder_thumbnail()


def display_dependency_panel(deps: DependencyInfo) -> None:
    st.subheader("Dependency Status")
    col1, col2 = st.columns(2)
    col1.write(f"ffmpeg: {'found' if deps.ffmpeg else 'not found'}")
    col1.caption(deps.ffmpeg or "Install on macOS with: brew install ffmpeg")
    col2.write(f"ffprobe: {'found' if deps.ffprobe else 'not found'}")
    col2.caption(deps.ffprobe or "Install on macOS with: brew install ffmpeg")
    if not deps.ffmpeg or not deps.ffprobe:
        st.warning("Install ffmpeg with `brew install ffmpeg`, then restart the Streamlit app. Metadata/contact-sheet analysis can still run where possible, but final video export requires ffmpeg.")


def process_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def terminate_job(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
        time.sleep(0.5)
        if process_running(pid):
            os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass
    append_log("Cancelled by user")
    write_status("Done", 100, status="cancelled", message="Cancelled by user")


def compute_processing_state(selected_files: list[Path]) -> str:
    running_pid = st.session_state.get("job_pid")
    status = read_status()
    status_name = str(status.get("status", "")).lower()
    if running_pid and process_running(int(running_pid)):
        return "RUNNING"
    if status_name == "done":
        return "DONE"
    if status_name == "failed":
        return "FAILED"
    if status_name == "cancelled":
        return "CANCELLED"
    return "READY" if selected_files else "IDLE"


def show_job_status(state: str) -> None:
    status = read_status()
    if not status and state not in {"IDLE", "READY"}:
        return
    st.subheader("Processing Status")
    st.write(f"State: **{state}**")
    if state in {"IDLE", "READY"}:
        st.info("Ready to generate once videos are selected." if state == "READY" else "Select source videos to begin.")
        return
    st.write(f"Current stage: **{status.get('stage', 'Done' if state == 'DONE' else 'idle')}**")
    st.progress(int(status.get("progress", 0)))
    elapsed = float(status.get("elapsed") or 0)
    eta = status.get("eta")
    eta_text = f"  Estimated time remaining: `{readable_duration(float(eta))}`" if eta is not None and state == "RUNNING" else ""
    st.write(f"Elapsed: `{readable_duration(elapsed)}`{eta_text}")
    if status.get("message"):
        st.caption(str(status["message"]))
    if state == "FAILED":
        st.error(f"Processing failed. See `{RUN_LOG_PATH}` for details.")
    elif state == "CANCELLED":
        st.warning("Cancelled by user.")
    if RUN_LOG_PATH.exists():
        lines = RUN_LOG_PATH.read_text(encoding="utf-8").splitlines()[-80:]
        st.text_area("Run log", "\n".join(lines), height=240)


def open_output_folder() -> None:
    open_folder(OUTPUT_DIR)


def build_job_config(
    source_dir: Path,
    selected_files: list[Path],
    target_duration: int,
    number_of_shots: int,
    min_clip_length: int,
    max_clip_length: int,
    motion_preference: str,
    blur_rejection: str,
    similarity_rejection: str,
    min_per_video: int,
    max_per_video: int,
    preset: str,
    transition_style: str,
    aspect_ratio: str,
    resolution: str,
    render_mode: str,
    look_for_subjects: bool,
    controls: dict[str, float],
    music_mode: str,
    music_file: str,
    music_mood: str,
    continue_without_music: bool,
) -> dict[str, Any]:
    return {
        "selected_source_folder": str(source_dir),
        "selected_files": [str(path) for path in selected_files],
        "target_duration": int(target_duration),
        "number_of_shots": int(number_of_shots),
        "min_clip_length": int(min_clip_length),
        "max_clip_length": int(max_clip_length),
        "motion_preference": motion_preference,
        "blur_rejection": blur_rejection,
        "similarity_rejection": similarity_rejection,
        "min_per_video": int(min_per_video),
        "max_per_video": int(max_per_video),
        "aesthetic_preset": preset,
        "preset": preset,
        "transition_style": transition_style,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "render_mode": render_mode,
        "look_for_subjects": bool(look_for_subjects),
        "manual_color_overrides": controls,
        "controls": controls,
        "music_mode": music_mode,
        "music_file": music_file,
        "music_mood": music_mood,
        "continue_without_music": bool(continue_without_music),
    }


def main() -> None:
    ensure_dirs()
    deps = detect_dependencies()
    st.set_page_config(page_title="Drone Rough Cut", layout="wide")
    st.title("Drone Hiking Rough Cut")

    if "custom_source_path" not in st.session_state:
        st.session_state.custom_source_path = ""
    if "music_file_path" not in st.session_state:
        st.session_state.music_file_path = ""
    if "music_mode" not in st.session_state:
        st.session_state.music_mode = "No music"
    if "video_rows" not in st.session_state:
        st.session_state.video_rows = []
    if "editor_nonce" not in st.session_state:
        st.session_state.editor_nonce = 0
    if "processing_state" not in st.session_state:
        st.session_state.processing_state = "IDLE"

    display_dependency_panel(deps)

    tab_source, tab_select, tab_settings, tab_discovery, tab_music, tab_generate, tab_results = st.tabs(
        ["1. Footage Source", "2. Select Videos", "3. Edit Settings", "4. Clip Discovery", "5. Music", "6. Generate", "7. Results"]
    )

    with tab_source:
        st.subheader("Footage Source")
        source_mode = st.radio("Source", ["Use default project folder", "Use custom local folder path"], horizontal=True)
        if source_mode == "Use custom local folder path" and st.button("Choose Folder"):
            selected_folder = open_system_folder_picker()
            if selected_folder:
                st.session_state.custom_source_path = selected_folder
        custom_source = st.text_input("Custom folder path", key="custom_source_path", disabled=source_mode == "Use default project folder")
        custom_source_entered = custom_source.strip()
        source_dir = RAW_DIR if source_mode == "Use default project folder" else Path(custom_source_entered).expanduser()
        source_valid = (
            (source_mode == "Use default project folder" or bool(custom_source_entered))
            and source_dir.exists()
            and source_dir.is_dir()
            and not is_inside_venv(source_dir)
        )
        st.info(f"Selected footage folder: `{source_dir}`")
        if not source_valid:
            st.warning("The selected footage folder does not exist, is not a folder, or is inside `.venv`.")
            clips: list[Path] = []
        else:
            clips = video_files(source_dir)
        col_a, col_b = st.columns(2)
        col_a.metric("Videos found", len(clips))
        col_b.metric("Supported formats", ".mp4 .mov .m4v")
        if not clips:
            st.warning("No `.mp4`, `.mov`, or `.m4v` videos were found in the selected folder.")

    scan_key = f"{source_dir}|{len(clips)}|{sum(int(p.stat().st_mtime) for p in clips) if clips else 0}"
    if st.session_state.get("scan_key") != scan_key:
        st.session_state.scan_key = scan_key
        with st.spinner("Generating thumbnails and reading metadata..."):
            st.session_state.video_rows = file_rows(clips, deps.ffprobe)

    with tab_select:
        st.subheader("Select Videos")
        st.caption("Videos are opt-in. Check only the source clips you want analyzed.")
        if clips:
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("Select all"):
                for row in st.session_state.video_rows:
                    row["include"] = True
                st.session_state.editor_nonce += 1
            if c2.button("Select none"):
                for row in st.session_state.video_rows:
                    row["include"] = False
                st.session_state.editor_nonce += 1
            if c3.button("Select shortest 10"):
                chosen = {row["path"] for row in sorted(st.session_state.video_rows, key=lambda item: item["duration_seconds"])[:10]}
                for row in st.session_state.video_rows:
                    row["include"] = row["path"] in chosen
                st.session_state.editor_nonce += 1
            if c4.button("Select newest 10"):
                chosen = {row["path"] for row in sorted(st.session_state.video_rows, key=lambda item: item["modified"], reverse=True)[:10]}
                for row in st.session_state.video_rows:
                    row["include"] = row["path"] in chosen
                st.session_state.editor_nonce += 1

            edited = st.data_editor(
                st.session_state.video_rows,
                key=f"video_selection_editor_{st.session_state.editor_nonce}",
                hide_index=True,
                disabled=["thumbnail", "filename", "duration", "duration_seconds", "resolution", "file_size_mb", "modified", "path"],
                column_config={
                    "include": st.column_config.CheckboxColumn("Include"),
                    "thumbnail": st.column_config.ImageColumn("Preview", width="small"),
                    "file_size_mb": st.column_config.NumberColumn("Size MB", format="%.1f"),
                    "path": None,
                    "modified": None,
                    "duration_seconds": None,
                },
                use_container_width=True,
            )
            st.session_state.video_rows = edited
        else:
            st.info("Choose a footage folder with supported videos first.")

        selected_files = [Path(row["path"]) for row in st.session_state.video_rows if row.get("include")]
        st.metric("Selected videos", f"{len(selected_files)} of {len(clips)}")
        if len(selected_files) > 20:
            st.warning("More than 20 videos are selected. Processing may take a long time.")

    with tab_settings:
        st.subheader("Edit Settings")
        target_duration = st.radio("Target duration", [30, 45, 60, 90], index=2, horizontal=True)
        left, right = st.columns(2)
        with left:
            render_mode = st.radio("Render Mode", ["Fast Preview", "Final Quality"], index=1, horizontal=True)
            if render_mode == "Fast Preview":
                st.caption("Prioritizes speed: cached/lower-rate analysis and 720p preview export to `rough_cut_preview.mp4`.")
            number_of_shots = st.slider("Number of shots", 6, 20, 12)
            min_clip_length = st.slider("Min clip length", 2, 6, 3)
            max_clip_length = st.slider("Max clip length", 4, 12, 7)
            motion_preference = st.selectbox("Motion preference", ["low", "medium", "high"], index=1)
            blur_rejection = st.selectbox("Blur rejection", ["low", "medium", "high"], index=1)
            similarity_rejection = st.selectbox("Similarity rejection", ["low", "medium", "high"], index=1)
            min_per_video = st.radio("Minimum clips per selected video", [0, 1], index=0, horizontal=True)
            max_per_video = st.slider("Maximum clips from one video", 1, 10, 4)
        with right:
            preset = st.selectbox("Aesthetic preset", ["Natural Documentary", "Moody Alpine", "Warm Travel", "High-Contrast Adventure"])
            transition_style = st.selectbox("Transition style", ["hard cuts", "short crossfades"])
            aspect_ratio = st.selectbox("Aspect ratio", ["16:9", "9:16"])
            resolution = st.selectbox("Export resolution", ["1080p", "4K"])
            if render_mode == "Fast Preview":
                st.info("Fast Preview overrides export resolution to 720p.")
            st.markdown("**Manual Color**")
            preset_control = preset_values(preset)
            exposure = st.slider("Exposure", -0.20, 0.20, float(preset_control["exposure"]), 0.01)
            contrast = st.slider("Contrast", 0.70, 1.50, float(preset_control["contrast"]), 0.01)
            saturation = st.slider("Saturation", 0.60, 1.60, float(preset_control["saturation"]), 0.01)
            temperature = st.slider("Temperature", -0.25, 0.25, float(preset_control["temperature"]), 0.01)
            sharpness = st.slider("Sharpness", 0.00, 1.00, float(preset_control["sharpness"]), 0.05)

    with tab_discovery:
        st.subheader("Clip Discovery")
        st.caption("Rank candidate moments for review in DaVinci. Labels are saved to `outputs/clip_review.csv`.")
        look_for_subjects = st.checkbox("Look for small moving subjects", value=False, help="Experimental hint only. Uses low-resolution frame differences and does not identify species.")
        discovery_limit = st.slider("Candidate rows to show", 20, 200, 80, 10)
        if not selected_files:
            st.info("Select videos first.")
        if selected_files and st.button("Analyze Selected Videos for Discovery", type="primary"):
            infos = [info for path in selected_files if (info := inspect_clip(path, deps.ffprobe))]
            clip_length = float(np.clip(target_duration / number_of_shots, min_clip_length, max_clip_length))
            if render_mode == "Fast Preview":
                clip_length = max(clip_length, 3.0)
            all_candidates: list[Candidate] = []
            fresh = cached = 0
            saved = 0.0
            with st.spinner("Analyzing candidate moments with cache..."):
                for info in infos:
                    candidates_for_video, from_cache, saved_seconds = analyze_clip_cached(info, clip_length, render_mode, look_for_subjects)
                    all_candidates.extend(candidates_for_video)
                    cached += int(from_cache)
                    fresh += int(not from_cache)
                    saved += saved_seconds
                all_candidates = score_candidates(all_candidates, motion_preference)
                rows = discovery_rows(all_candidates, discovery_limit)
                st.session_state.discovery_rows = rows
                save_clip_review(rows)
            st.success(f"Discovery complete: {fresh} videos analyzed fresh, {cached} loaded from cache, estimated {saved:.1f}s saved.")

        review_rows = st.session_state.get("discovery_rows") or load_clip_review()
        if review_rows:
            labels = ["Must review", "Maybe", "Reject", "Possible animal/bird", "Landscape reveal", "Janky control", "Good opening shot", "Good closing shot"]
            edited_review = st.data_editor(
                review_rows,
                hide_index=True,
                key="clip_discovery_editor",
                disabled=[
                    "rank",
                    "thumbnail",
                    "source_filename",
                    "source_path",
                    "start_time",
                    "end_time",
                    "duration",
                    "motion_score",
                    "sharpness_score",
                    "stability_score",
                    "novelty_score",
                    "interestingness_score",
                    "reason",
                    "subject_x",
                    "subject_y",
                ],
                column_config={
                    "label": st.column_config.SelectboxColumn("Label", options=labels),
                    "thumbnail": st.column_config.ImageColumn("Preview", width="small"),
                    "source_path": None,
                    "subject_x": None,
                    "subject_y": None,
                },
                use_container_width=True,
            )
            st.session_state.discovery_rows = edited_review
            save_clip_review(edited_review)
            export_cols = st.columns(2)
            if export_cols[0].button("Export Must Review clips", disabled=not deps.ffmpeg):
                exported = export_review_clips(edited_review, deps.ffmpeg, subject_focus=False)
                save_davinci_review_list(exported)
                st.success(f"Exported {len(exported)} clips to `{MUST_REVIEW_DIR}` and wrote `outputs/davinci_review_list.csv`.")
            if export_cols[1].button("Create subject-focused preview", disabled=not deps.ffmpeg):
                st.warning("Experimental: crop/zoom is based on a rough moving-subject hint and may be wrong.")
                exported = export_review_clips(edited_review, deps.ffmpeg, subject_focus=True)
                st.success(f"Exported {len(exported)} subject-focused previews to `{SUBJECT_FOCUS_DIR}`.")

    with tab_music:
        st.subheader("Music")
        music_mode = st.radio(
            "Music mode",
            ["No music", "Use my own music file", "Auto-select music"],
            horizontal=True,
            key="music_mode",
        )
        music_mood = "cinematic"
        music_path_valid = False
        auto_music_row: dict[str, str] | None = None
        continue_without_music = False
        if music_mode == "No music":
            st.info("Exports a silent video.")
        elif music_mode == "Use my own music file":
            st.info("Uses a local `.mp3`, `.wav`, `.m4a`, `.flac`, or `.ogg` file selected by you. The app trims it to the final video duration and adds short fades.")
            if st.button("Choose Music File"):
                chosen_file = open_system_file_picker()
                if chosen_file:
                    st.session_state.music_file_path = chosen_file
            uploaded_music = st.file_uploader("Upload/copy a music file into the local library", type=["mp3", "wav", "m4a", "flac", "ogg"])
            if uploaded_music is not None:
                target = MUSIC_LIBRARY_DIR / uploaded_music.name
                target.write_bytes(uploaded_music.getbuffer())
                st.session_state.music_file_path = str(target)
                st.success(f"Imported `{target.name}` to `{MUSIC_LIBRARY_DIR}`.")
            st.text_input("Music file path", key="music_file_path")
            selected_music_path = Path(st.session_state.music_file_path).expanduser() if st.session_state.music_file_path.strip() else None
            music_path_valid = bool(selected_music_path and is_valid_audio_file(selected_music_path))
            if music_path_valid and selected_music_path:
                st.success(f"Selected music file: `{selected_music_path.name}`")
            elif st.session_state.music_file_path.strip():
                st.error("The selected music file does not exist or is not `.mp3`, `.wav`, `.m4a`, `.flac`, or `.ogg`.")
        elif music_mode == "Auto-select music":
            st.info("Looks for matching tracks in `./music_library/` and automatically picks a suitable local royalty-free/public-domain-safe track for the selected mood.")
            music_mood = st.selectbox("Desired music mood", ["cinematic", "calm", "epic", "dark", "uplifting", "ambient"])
            library_tracks = load_music_library()
            st.write(f"Library tracks found: **{len(library_tracks)}** in `{MUSIC_LIBRARY_DIR}`")
            auto_music_row = choose_library_music(music_mood, int(target_duration), deps.ffprobe)
            if auto_music_row:
                st.success(f"Auto-selected track: {describe_music_row(auto_music_row)}")
            else:
                st.warning("No matching music found. Add tracks to `./music_library/` or use the music importer.")
                continue_without_music = st.checkbox("Continue without music", value=False)
                if st.button("Switch to Use my own music file"):
                    st.session_state.music_mode = "Use my own music file"
                    st.rerun()
                if st.button("Open music_library folder"):
                    open_folder(MUSIC_LIBRARY_DIR)

            st.markdown("**Music Library Setup**")
            st.write(f"Library folder: `{MUSIC_LIBRARY_DIR}`")
            if st.button("Open music_library folder", key="open_music_library_setup"):
                open_folder(MUSIC_LIBRARY_DIR)
            st.caption("Drop `.mp3`, `.wav`, `.m4a`, `.flac`, or `.ogg` files there. Add optional metadata in `music_library/music_library.csv` with columns: filename,title,artist,mood,bpm,license,source_url,attribution_required,attribution_text.")

            with st.expander("Import music from URL"):
                st.warning("Only use direct audio URLs for tracks you have rights to use. This does not scrape sites or bypass website terms.")
                import_url = st.text_input("Direct audio URL")
                import_title = st.text_input("Title")
                import_artist = st.text_input("Artist")
                import_mood = st.selectbox("Mood", ["cinematic", "calm", "epic", "dark", "uplifting", "ambient"], key="import_music_mood")
                import_license = st.text_input("License")
                attribution_required = st.checkbox("Attribution required")
                attribution_text = st.text_area("Attribution text")
                if st.button("Import URL to music_library"):
                    try:
                        imported = import_music_from_url(
                            import_url,
                            {
                                "title": import_title,
                                "artist": import_artist,
                                "mood": import_mood,
                                "license": import_license,
                                "attribution_required": "true" if attribution_required else "false",
                                "attribution_text": attribution_text,
                            },
                        )
                        st.success(f"Imported `{imported.name}`.")
                    except Exception as exc:
                        st.error(str(exc))

        will_have_music = (
            (music_mode == "Use my own music file" and music_path_valid)
            or (music_mode == "Auto-select music" and auto_music_row is not None)
        )
        st.markdown("**Music Summary**")
        st.write(f"Music mode: **{music_mode}**")
        if music_mode == "Auto-select music":
            st.write(f"Selected mood: **{music_mood}**")
            st.write(f"Track selected: **{describe_music_row(auto_music_row)}**")
        elif music_mode == "Use my own music file":
            st.write(f"Track selected: **{Path(st.session_state.music_file_path).name if music_path_valid else 'None'}**")
        st.write("Final video will include music." if will_have_music else "Final video will be silent.")
    # Defaults for first Streamlit script pass if a later tab has not rendered values yet.
    preset_control = preset_values(preset)
    exposure = float(locals().get("exposure", preset_control["exposure"]))
    contrast = float(locals().get("contrast", preset_control["contrast"]))
    saturation = float(locals().get("saturation", preset_control["saturation"]))
    temperature = float(locals().get("temperature", preset_control["temperature"]))
    sharpness = float(locals().get("sharpness", preset_control["sharpness"]))

    state = compute_processing_state(selected_files)
    st.session_state.processing_state = state

    with tab_generate:
        st.subheader("Generate")
        status_cols = st.columns(4)
        status_cols[0].metric("State", state)
        status_cols[1].metric("Selected videos", len(selected_files))
        status_cols[2].metric("Target", f"{target_duration}s")
        status_cols[3].metric("Shots", number_of_shots)
        processing_backend = st.radio(
            "Processing backend",
            ["Local Mac", "Remote worker / external compute (experimental)"],
            index=0,
        )
        if processing_backend == "Remote worker / external compute (experimental)":
            st.warning("Remote processing may upload private footage to an external machine. Use only if you trust the provider and understand the cost.")
            st.info("Remote processing is not configured yet. You can export a job package for external compute.")

        can_export = bool(deps.ffmpeg)
        if not selected_files:
            st.warning("Select at least one video before generating.")
        if not can_export:
            st.warning("ffmpeg is missing. Install with `brew install ffmpeg`, restart Streamlit, then export.")
        if len(selected_files) > 20:
            st.warning("Large selections can take a long time. Consider selecting fewer videos for a faster rough cut.")
        music_blocks_generation = False
        if music_mode == "Use my own music file" and not music_path_valid:
            music_blocks_generation = True
            st.warning("Choose a valid `.mp3`, `.wav`, `.m4a`, `.flac`, or `.ogg` file, or switch music mode before generating.")
        if music_mode == "Auto-select music" and auto_music_row is None and not continue_without_music:
            music_blocks_generation = True
            st.warning("No matching music found. Add tracks to `./music_library/`, switch music mode, or choose Continue without music.")

        st.markdown("**Music Summary**")
        st.write(f"Mode: **{music_mode}**")
        if music_mode == "Auto-select music":
            st.write(f"Mood: **{music_mood}**")
            st.write(f"Track: **{describe_music_row(auto_music_row)}**")
        elif music_mode == "Use my own music file":
            st.write(f"Track: **{Path(st.session_state.music_file_path).name if music_path_valid else 'None'}**")
        st.write("Final video will include music." if will_have_music else "Final video will be silent.")

        running_pid = st.session_state.get("job_pid")
        if state == "RUNNING":
            if st.button("Cancel Processing", type="secondary"):
                terminate_job(int(running_pid))
                st.session_state.job_pid = None
                st.rerun()

        config = build_job_config(
            source_dir=source_dir,
            selected_files=selected_files,
            target_duration=target_duration,
            number_of_shots=number_of_shots,
            min_clip_length=min_clip_length,
            max_clip_length=max_clip_length,
            motion_preference=motion_preference,
            blur_rejection=blur_rejection,
            similarity_rejection=similarity_rejection,
            min_per_video=min_per_video,
            max_per_video=max_per_video,
            preset=preset,
            transition_style=transition_style,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            render_mode=render_mode,
            look_for_subjects=look_for_subjects,
            controls={"exposure": exposure, "contrast": contrast, "saturation": saturation, "temperature": temperature, "sharpness": sharpness},
            music_mode=music_mode,
            music_file=st.session_state.music_file_path,
            music_mood=music_mood,
            continue_without_music=bool(continue_without_music),
        )

        if processing_backend == "Remote worker / external compute (experimental)":
            if st.button("Export Remote Job Package", disabled=not selected_files):
                paths = export_remote_job_package(
                    OUTPUT_DIR / "remote_job_package",
                    config,
                    st.session_state.video_rows,
                    ROOT / "requirements.txt",
                )
                st.success(f"Remote job package written to `{OUTPUT_DIR / 'remote_job_package'}`.")
                st.write(paths)

        generate_disabled = (
            processing_backend != "Local Mac"
            or state == "RUNNING"
            or not selected_files
            or not can_export
            or music_blocks_generation
        )
        if st.button("Generate Rough Cut", type="primary", disabled=generate_disabled):
            CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
            write_status("Scanning videos", 1, status="running", message="Starting job", started_at=time.time())
            RUN_LOG_PATH.write_text("", encoding="utf-8")
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(CONFIG_PATH)], cwd=str(ROOT), start_new_session=True)
            st.session_state.job_pid = process.pid
            st.session_state.processing_state = "RUNNING"
            st.rerun()

        show_job_status(state)
        if state == "RUNNING":
            time.sleep(1)
            st.rerun()

    with tab_results:
        st.subheader("Results")
        status = read_status()
        final_output = output_video_path(render_mode)
        if state == "DONE":
            elapsed = float(status.get("elapsed") or 0)
            decisions = load_edit_decisions()
            used_sources = {row.get("source_filename") for row in decisions}
            st.success("✅ DONE — rough cut exported successfully")
            summary = st.columns(4)
            summary[0].metric("Elapsed", readable_duration(elapsed))
            summary[1].metric("Source videos used", len(used_sources))
            summary[2].metric("Final clips", len(decisions))
            summary[3].metric("Output", "ready" if final_output.exists() else "analysis only")
            st.write(f"Output file: `{final_output}`")
            if final_output.exists() and final_output.stat().st_size > 0:
                st.video(str(final_output))
                try:
                    st.download_button(
                        f"Download {final_output.name}",
                        data=final_output.read_bytes(),
                        file_name=final_output.name,
                        mime="video/mp4",
                    )
                except OSError as exc:
                    st.error(f"Could not prepare download: {exc}")
            elif final_output.exists():
                st.error(f"`{final_output}` exists but is empty, so it cannot be downloaded.")
            music_used_path = OUTPUT_DIR / "music_used.txt"
            if music_used_path.exists():
                st.markdown("**Music Used**")
                st.text(music_used_path.read_text(encoding="utf-8"))
                st.caption(f"Details: `{music_used_path}`")
            if st.button("Open output folder"):
                open_output_folder()
            show_performance_summary()
            if decisions:
                st.markdown("**Selected Clips / Edit Decisions**")
                st.dataframe(
                    decisions,
                    hide_index=True,
                    column_config={
                        "thumbnail": st.column_config.ImageColumn("Preview", width="small"),
                        "clip_number": st.column_config.NumberColumn("Clip #"),
                    },
                    use_container_width=True,
                )
        elif state == "FAILED":
            st.error(f"Processing failed. See `{RUN_LOG_PATH}` for details.")
            show_job_status(state)
            show_performance_summary()
        elif state == "CANCELLED":
            st.warning("Cancelled by user.")
            show_job_status(state)
            show_performance_summary()
        else:
            st.info("No completed export yet.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    if args.worker:
        run_worker(args.worker)
    else:
        main()
