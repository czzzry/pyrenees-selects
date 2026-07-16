from __future__ import annotations

import math
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from .media import MediaToolError, require_media_tools


ANALYSIS_VERSION = 1
FRAME_WIDTH = 160
FRAME_HEIGHT = 90
FRAME_BYTES = FRAME_WIDTH * FRAME_HEIGHT
SAMPLE_SECONDS = 2.0
TARGET_SECONDS = 8.0


@dataclass(frozen=True)
class AnalyzedRange:
    start_seconds: float
    duration: float
    score: float
    reason: str


def _frame_metrics(frame: bytes, previous: bytes | None) -> tuple[float, float, float]:
    mean = sum(frame) / len(frame)
    gradient_total = 0
    gradient_count = 0
    for index in range(0, len(frame) - 1, 4):
        if index % FRAME_WIDTH != FRAME_WIDTH - 1:
            gradient_total += abs(frame[index] - frame[index + 1])
            gradient_count += 1
    gradient = gradient_total / max(1, gradient_count)
    if previous is None:
        motion = 6.0
    else:
        motion = sum(abs(frame[index] - previous[index]) for index in range(0, len(frame), 4)) / (len(frame) / 4)
    return mean, gradient, motion


def _window_score(window: list[tuple[float, float, float]]) -> tuple[float, dict[str, float]]:
    means = [item[0] for item in window]
    gradients = [item[1] for item in window]
    motions = [item[2] for item in window]
    mean = sum(means) / len(means)
    exposure = max(0.0, 1.0 - abs(mean - 125.0) / 105.0)
    detail = min(1.0, (sum(gradients) / len(gradients)) / 18.0)
    motion = sum(motions) / len(motions)
    if motion < 1.2:
        movement = 0.25
    elif motion <= 18.0:
        movement = 1.0
    else:
        movement = max(0.15, 1.0 - (motion - 18.0) / 38.0)
    consistency = max(0.0, 1.0 - (max(means) - min(means)) / 65.0)
    score = 0.34 * exposure + 0.31 * detail + 0.20 * movement + 0.15 * consistency
    return score, {"exposure": exposure, "detail": detail, "movement": movement, "consistency": consistency}


def _reason(metrics: dict[str, float]) -> str:
    strengths = sorted(metrics, key=metrics.get, reverse=True)[:2]
    labels = {
        "exposure": "balanced exposure",
        "detail": "strong visible detail",
        "movement": "steady scenic movement",
        "consistency": "a sustained, uninterrupted view",
    }
    return f"Surfaced by sparse analysis for {labels[strengths[0]]} and {labels[strengths[1]]}."


def analyze_video(source: Path, duration: float, cancel: Event | None = None, ffmpeg: str | None = None) -> AnalyzedRange:
    if duration <= 0:
        raise ValueError("duration must be positive")
    tool = ffmpeg or require_media_tools()[0]
    command = [tool, "-v", "error"]
    if platform.system() == "Darwin":
        command.extend(["-hwaccel", "videotoolbox"])
    command.extend([
        "-i", str(source), "-an", "-sn",
        "-vf", f"fps=1/{SAMPLE_SECONDS:g},scale={FRAME_WIDTH}:{FRAME_HEIGHT}:force_original_aspect_ratio=decrease,pad={FRAME_WIDTH}:{FRAME_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ])
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    metrics: list[tuple[float, float, float]] = []
    previous: bytes | None = None
    try:
        assert process.stdout is not None
        while True:
            if cancel and cancel.is_set():
                process.terminate()
                raise InterruptedError("Analysis cancelled.")
            frame = process.stdout.read(FRAME_BYTES)
            if not frame:
                break
            if len(frame) != FRAME_BYTES:
                raise MediaToolError(f"Incomplete analysis frame from {source.name}.")
            metrics.append(_frame_metrics(frame, previous))
            previous = frame
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        if process.wait() != 0:
            raise MediaToolError(f"Could not analyze {source.name}: {stderr[-300:]}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    if not metrics:
        raise MediaToolError(f"No analysis samples could be read from {source.name}.")
    window_size = max(1, min(len(metrics), math.ceil(TARGET_SECONDS / SAMPLE_SECONDS)))
    margin = 2 if len(metrics) >= window_size + 4 else 0
    starts = range(margin, max(margin + 1, len(metrics) - window_size - margin + 1))
    best_index = 0
    best_score = -1.0
    best_metrics: dict[str, float] = {}
    for index in starts:
        score, components = _window_score(metrics[index:index + window_size])
        if score > best_score:
            best_index, best_score, best_metrics = index, score, components
    candidate_duration = min(TARGET_SECONDS, duration)
    start_seconds = min(best_index * SAMPLE_SECONDS, max(0.0, duration - candidate_duration))
    return AnalyzedRange(start_seconds, candidate_duration, round(best_score, 4), _reason(best_metrics))
