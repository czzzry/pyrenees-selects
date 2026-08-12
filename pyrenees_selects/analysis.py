from __future__ import annotations

import math
import platform
import subprocess
from array import array
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any

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


@dataclass(frozen=True)
class AnalyzedCandidate:
    in_us: int
    out_us: int
    score: float
    components: dict[str, float]
    rationale: str


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
        "audio_activity": "measured audio activity",
    }
    return f"Suggested from measured signals: {labels[strengths[0]]} and {labels[strengths[1]]}."


def _visual_samples(source: Path, cancel: Event | None, tool: str) -> list[tuple[float, float, float]]:
    command = [tool, "-v", "error"]
    if platform.system() == "Darwin":
        command.extend(["-hwaccel", "videotoolbox"])
    command.extend([
        "-i", str(source), "-an", "-sn",
        "-vf", f"fps=1/{SAMPLE_SECONDS:g}:round=up,scale={FRAME_WIDTH}:{FRAME_HEIGHT}:force_original_aspect_ratio=decrease,pad={FRAME_WIDTH}:{FRAME_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray",
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
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
    return metrics


def _audio_samples(source: Path, cancel: Event | None, tool: str) -> list[float]:
    sample_rate = 1_000
    bytes_per_window = int(sample_rate * SAMPLE_SECONDS * 2)
    command = [
        tool, "-v", "error", "-i", str(source), "-vn", "-sn", "-map", "0:a:0?",
        "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    activity: list[float] = []
    try:
        assert process.stdout is not None
        while True:
            if cancel and cancel.is_set():
                process.terminate()
                raise InterruptedError("Analysis cancelled.")
            chunk = process.stdout.read(bytes_per_window)
            if not chunk:
                break
            usable = chunk[: len(chunk) - (len(chunk) % 2)]
            values = array("h")
            values.frombytes(usable)
            rms = math.sqrt(sum(value * value for value in values) / max(1, len(values)))
            activity.append(min(1.0, rms / 8_000.0))
        if process.wait() != 0:
            # Optional audio absence is not a failed visual analysis.
            return []
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
    return activity


def candidates_from_metrics(
    visual: list[tuple[float, float, float]],
    *,
    duration: float,
    budget_seconds: float,
    shot_min_seconds: float,
    shot_max_seconds: float,
    audio: list[float] | None = None,
    audio_preference: str = "visual",
) -> list[AnalyzedCandidate]:
    if not visual:
        raise MediaToolError("No analysis samples could be read.")
    if duration <= 0 or budget_seconds <= 0:
        return []
    if duration < shot_min_seconds:
        score, components = _window_score(visual)
        if audio and audio_preference != "visual":
            components["audio_activity"] = sum(audio) / len(audio)
            score = score * 0.88 + components["audio_activity"] * 0.12
        return [AnalyzedCandidate(0, max(1, round(duration * 1_000_000)), round(score, 4), components, _reason(components))]
    if budget_seconds < shot_min_seconds:
        # Do not manufacture a minimum-length shot that exceeds the entire
        # candidate budget. The plan reports the resulting shortfall honestly.
        return []

    requested = math.floor(budget_seconds / shot_min_seconds)
    window_seconds = min(shot_max_seconds, max(shot_min_seconds, budget_seconds / requested))
    window_size = max(1, math.ceil(window_seconds / SAMPLE_SECONDS))
    possibilities: list[tuple[float, int, dict[str, float]]] = []
    for index in range(0, max(1, len(visual) - window_size + 1)):
        segment = visual[index:index + window_size]
        if not segment:
            continue
        score, components = _window_score(segment)
        if audio and audio_preference != "visual":
            audio_window = audio[index:index + window_size]
            if audio_window:
                components["audio_activity"] = sum(audio_window) / len(audio_window)
                weight = 0.12 if audio_preference == "speech_and_distinctive" else 0.06
                score = score * (1 - weight) + components["audio_activity"] * weight
        possibilities.append((score, index, components))

    chosen: list[AnalyzedCandidate] = []
    occupied: list[tuple[float, float]] = []
    for score, index, components in sorted(possibilities, key=lambda item: (-item[0], item[1])):
        start = min(index * SAMPLE_SECONDS, max(0.0, duration - window_seconds))
        end = min(duration, start + window_seconds)
        if any(start < other_end + SAMPLE_SECONDS and end + SAMPLE_SECONDS > other_start for other_start, other_end in occupied):
            continue
        occupied.append((start, end))
        chosen.append(AnalyzedCandidate(
            round(start * 1_000_000),
            round(end * 1_000_000),
            round(score, 4),
            {key: round(value, 4) for key, value in components.items()},
            _reason(components),
        ))
        if len(chosen) >= requested:
            break
    return sorted(chosen, key=lambda candidate: candidate.in_us)


def analyze_video_candidates(
    source: Path,
    duration: float,
    *,
    budget_seconds: float,
    shot_min_seconds: float,
    shot_max_seconds: float,
    audio_preference: str = "visual",
    has_audio: bool = False,
    cancel: Event | None = None,
    ffmpeg: str | None = None,
) -> list[AnalyzedCandidate]:
    tool = ffmpeg or require_media_tools()[0]
    visual = _visual_samples(source, cancel, tool)
    if not visual:
        raise MediaToolError(f"No analysis samples could be read from {source.name}.")
    audio = _audio_samples(source, cancel, tool) if has_audio and audio_preference != "visual" else []
    return candidates_from_metrics(
        visual,
        duration=duration,
        budget_seconds=budget_seconds,
        shot_min_seconds=shot_min_seconds,
        shot_max_seconds=shot_max_seconds,
        audio=audio,
        audio_preference=audio_preference,
    )


def analyze_video(source: Path, duration: float, cancel: Event | None = None, ffmpeg: str | None = None) -> AnalyzedRange:
    if duration <= 0:
        raise ValueError("duration must be positive")
    candidate = analyze_video_candidates(
        source,
        duration,
        budget_seconds=min(TARGET_SECONDS, duration),
        shot_min_seconds=min(TARGET_SECONDS, duration),
        shot_max_seconds=min(TARGET_SECONDS, duration),
        cancel=cancel,
        ffmpeg=ffmpeg,
    )[0]
    return AnalyzedRange(
        candidate.in_us / 1_000_000,
        (candidate.out_us - candidate.in_us) / 1_000_000,
        candidate.score,
        candidate.rationale,
    )
