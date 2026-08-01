#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyrenees_selects.integrated_plan import INTEGRATED_DRONE_PHONE_ORDER
from pyrenees_selects.media import concatenate_video_clips, has_audio_stream, probe_video
from pyrenees_selects.server import build_application


DRONE_RENDER_ID = "c203acd1249a"
PHONE_RENDER_ID = "8ebdb64e7215"
NORTH_STAR_RENDER_ID = "9f88893e5b6c"
LONG_RENDER_ID = "1b62ea0ca155"
FFMPEG = (ROOT / "build" / "media-tools" / "ffmpeg").resolve()
FFPROBE = (ROOT / "build" / "media-tools" / "ffprobe").resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _single_match(directory: Path, pattern: str) -> Path:
    matches = list(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one cached clip matching {pattern}, found {len(matches)}.")
    return matches[0].resolve(strict=True)


def _drone_clip(app_root: Path, item: dict[str, Any]) -> Path:
    candidate_id = int(item["candidate_id"])
    drone_cache = app_root / "cache" / "pyrenees-2024"
    if item.get("signature_moment"):
        return (drone_cache / "signature" / "candidate-078-faithful-extended-360p.mp4").resolve(strict=True)
    source_kind = item["source_kind"]
    if source_kind == "north_star":
        return _single_match(
            drone_cache / "treated" / NORTH_STAR_RENDER_ID,
            f"*-{candidate_id:03d}-*.mp4",
        )
    if source_kind == "long_cut":
        return _single_match(
            drone_cache / "treated-long" / LONG_RENDER_ID,
            f"*-{candidate_id:03d}-*.mp4",
        )
    if source_kind == "hybrid_refinement":
        return _single_match(
            drone_cache / "treated-hybrid" / DRONE_RENDER_ID,
            f"{candidate_id:03d}-*.mp4",
        )
    raise RuntimeError(f"Unknown drone source kind: {source_kind}")


def _phone_clip(app_root: Path, item: dict[str, Any]) -> Path:
    candidate_id = int(item["candidate_id"])
    return _single_match(
        app_root / "cache" / "project-7f3d797737d9" / "phone-treated" / PHONE_RENDER_ID,
        f"*-{candidate_id:03d}-*.mp4",
    )


def _add_silent_audio(source: Path, destination: Path, duration: float) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    temporary = destination.with_suffix(".partial.mp4")
    temporary.unlink(missing_ok=True)
    command = [
        str(FFMPEG), "-nostdin", "-v", "error",
        "-i", str(source),
        "-f", "lavfi", "-t", f"{duration:.6f}", "-i", "anullsrc=r=48000:cl=stereo",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-t", f"{duration:.6f}",
        "-movflags", "+faststart", "-y", str(temporary),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=120)
        temporary.replace(destination)
    except subprocess.SubprocessError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Could not prepare drone shot {source.name} for the combined cut.") from exc
    return destination


def main() -> None:
    started = time.monotonic()
    if not FFMPEG.is_file() or not FFPROBE.is_file():
        raise RuntimeError("The local FFmpeg tools are not available.")
    application = build_application()
    app_root = application.paths.root
    exports = app_root / "exports"
    drone_manifest_path = exports / f"Pyrenees-treated-hybrid-with-extended-bird-{DRONE_RENDER_ID}.json"
    phone_manifest_path = exports / f"Pyrenees-phone-treated-rough-cut-{PHONE_RENDER_ID}.json"
    drone_manifest = json.loads(drone_manifest_path.read_text(encoding="utf-8"))
    phone_manifest = json.loads(phone_manifest_path.read_text(encoding="utf-8"))
    drone_items = {int(item["candidate_id"]): item for item in drone_manifest["items"]}
    phone_items = {int(item["candidate_id"]): item for item in phone_manifest["items"]}
    requested_drone_ids = {candidate_id for origin, candidate_id in INTEGRATED_DRONE_PHONE_ORDER if origin == "drone"}
    requested_phone_ids = {candidate_id for origin, candidate_id in INTEGRATED_DRONE_PHONE_ORDER if origin == "phone"}
    if requested_drone_ids != set(drone_items):
        raise RuntimeError("The integrated plan no longer matches the approved drone hybrid.")
    if requested_phone_ids != set(phone_items):
        raise RuntimeError("The integrated plan no longer matches the approved phone storyboard.")

    seed_items: list[dict[str, Any]] = []
    for position, (origin, candidate_id) in enumerate(INTEGRATED_DRONE_PHONE_ORDER, start=1):
        item = drone_items[candidate_id] if origin == "drone" else phone_items[candidate_id]
        duration = float(item["output_duration"] if origin == "drone" else item["target_duration"])
        seed_items.append({
            "position": position,
            "origin": origin,
            "candidate_id": candidate_id,
            "duration": duration,
            "filename": item["filename"],
        })
    render_id = hashlib.sha256(
        json.dumps(seed_items, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12]
    cache = app_root / "cache" / "integrated-drone-phone" / render_id
    destination = exports / f"Pyrenees-combined-drone-phone-rough-cut-{render_id}.mp4"
    manifest_path = exports / f"Pyrenees-combined-drone-phone-rough-cut-{render_id}.json"
    status_path = app_root / "integrated-rough-cut-status.json"
    cache.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)

    clips: list[Path] = []
    manifest_items: list[dict[str, Any]] = []
    total = len(INTEGRATED_DRONE_PHONE_ORDER)
    started_at = _now()
    for position, (origin, candidate_id) in enumerate(INTEGRATED_DRONE_PHONE_ORDER, start=1):
        item = drone_items[candidate_id] if origin == "drone" else phone_items[candidate_id]
        duration = float(item["output_duration"] if origin == "drone" else item["target_duration"])
        source = _drone_clip(app_root, item) if origin == "drone" else _phone_clip(app_root, item)
        if origin == "drone":
            clip = _add_silent_audio(
                source,
                cache / f"{position:02d}-drone-{candidate_id:03d}.mp4",
                duration,
            )
        else:
            if not has_audio_stream(source, ffprobe=str(FFPROBE)):
                raise RuntimeError(f"Phone shot {candidate_id} has lost its audio track.")
            clip = source
        clips.append(clip)
        manifest_items.append({
            "position": position,
            "origin": origin,
            "candidate_id": candidate_id,
            "filename": item["filename"],
            "duration": duration,
            "source_clip": str(source),
        })
        status_path.write_text(json.dumps({
            "state": "running",
            "render_id": render_id,
            "processed": position,
            "total": total,
            "current": f"{origin} {candidate_id}",
            "started_at": started_at,
            "updated_at": _now(),
        }, indent=2), encoding="utf-8")
        print(f"[{position:02d}/{total}] {origin.title()} candidate {candidate_id:03d}", flush=True)

    print("Assembling the approved drone and phone footage into one film…", flush=True)
    concatenate_video_clips(clips, destination, ffmpeg=str(FFMPEG), timeout_seconds=600)
    output = probe_video(destination, ffprobe=str(FFPROBE))
    if not has_audio_stream(destination, ffprobe=str(FFPROBE)):
        raise RuntimeError("The combined rough cut has no audio track.")
    expected_duration = sum(float(item["duration"]) for item in manifest_items)
    if abs(output.duration - expected_duration) > 0.5:
        raise RuntimeError(
            f"The combined rough cut is {output.duration:.2f}s; expected {expected_duration:.2f}s."
        )
    elapsed = time.monotonic() - started
    manifest = {
        "render_id": render_id,
        "created_at": _now(),
        "output": str(destination),
        "output_duration": output.duration,
        "expected_duration": expected_duration,
        "output_size_bytes": output.size_bytes,
        "elapsed_seconds": round(elapsed, 3),
        "drone_baseline_render_id": DRONE_RENDER_ID,
        "phone_insert_render_id": PHONE_RENDER_ID,
        "audio_included": True,
        "items": manifest_items,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    status_path.write_text(json.dumps({
        "state": "complete",
        "render_id": render_id,
        "processed": total,
        "total": total,
        "output": str(destination),
        "duration": output.duration,
        "elapsed_seconds": round(elapsed, 3),
        "finished_at": _now(),
    }, indent=2), encoding="utf-8")
    print(f"OUTPUT={destination}", flush=True)
    print(f"MANIFEST={manifest_path}", flush=True)
    print(f"DURATION={output.duration:.3f}s", flush=True)
    print(f"ELAPSED={elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    main()
