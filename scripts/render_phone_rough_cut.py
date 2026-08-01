#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyrenees_selects.media import (
    cache_key,
    concatenate_video_clips,
    has_audio_stream,
    probe_video,
    render_treated_clip,
)
from pyrenees_selects.phone_treatment_plan import PHONE_TREATMENTS
from pyrenees_selects.server import build_application


PROJECT_ID = "project-7f3d797737d9"
VARIANT_SECONDS = 120
FFMPEG = (ROOT / "build" / "media-tools" / "ffmpeg").resolve()
FFPROBE = (ROOT / "build" / "media-tools" / "ffprobe").resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    started = time.monotonic()
    if not FFMPEG.is_file() or not FFPROBE.is_file():
        raise RuntimeError("The local FFmpeg tools are not available.")
    application = build_application()
    project = application.store.project(PROJECT_ID)
    if not project:
        raise RuntimeError("The phone-footage project is not available.")
    items = application.store.storyboard_items(PROJECT_ID, VARIANT_SECONDS)
    approved = [item for item in items if item["review_state"] == "approved"]
    if not items or len(approved) != len(items):
        raise RuntimeError("Complete the phone storyboard review before rendering.")

    treatments = {treatment.candidate_id: treatment for treatment in PHONE_TREATMENTS}
    candidate_ids = [int(item["candidate_id"]) for item in approved]
    if len(treatments) != len(PHONE_TREATMENTS):
        raise RuntimeError("The phone treatment plan contains a duplicate candidate.")
    if set(candidate_ids) != set(treatments):
        raise RuntimeError("The phone treatment plan does not match the approved storyboard.")
    if abs(sum(float(item["target_duration"]) for item in approved) - VARIANT_SECONDS) > 0.001:
        raise RuntimeError("The approved phone storyboard no longer totals two minutes.")

    manifest_items: list[dict[str, object]] = []
    for item in approved:
        candidate_id = int(item["candidate_id"])
        source_duration = float(item["proposed_duration"])
        target_duration = float(item["target_duration"])
        treatment = treatments[candidate_id]
        manifest_items.append({
            "position": int(item["position"]),
            "candidate_id": candidate_id,
            "filename": item["filename"],
            "source_start": float(item["proposed_start_seconds"]),
            "source_duration": source_duration,
            "target_duration": target_duration,
            "playback_rate": source_duration / target_duration,
            "treatment_note": item["treatment"],
            "owner_comment": item["note"],
            **treatment.to_dict(),
        })

    manifest_seed = json.dumps(manifest_items, sort_keys=True, ensure_ascii=False).encode("utf-8")
    render_id = hashlib.sha256(manifest_seed).hexdigest()[:12]
    treated_cache = application.paths.cache / PROJECT_ID / "phone-treated" / render_id
    exports = application.paths.root / "exports"
    destination = exports / f"Pyrenees-phone-treated-rough-cut-{render_id}.mp4"
    manifest_path = exports / f"Pyrenees-phone-treated-rough-cut-{render_id}.json"
    status_path = application.paths.root / "phone-treated-rough-cut-status.json"
    treated_cache.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)

    clips: list[Path] = []
    timings: list[dict[str, object]] = []
    total = len(approved)
    status_started_at = _now()
    for position, item in enumerate(approved, start=1):
        candidate_id = int(item["candidate_id"])
        treatment = treatments[candidate_id]
        source = Path(item["path"]).resolve(strict=True)
        if source.parent != Path(project["source_dir"]).resolve(strict=True):
            raise RuntimeError(f"Candidate {candidate_id} is outside the phone-footage folder.")
        source_start = float(item["proposed_start_seconds"])
        source_duration = float(item["proposed_duration"])
        target_duration = float(item["target_duration"])
        playback_rate = source_duration / target_duration
        if source_start + source_duration > float(item["source_duration"]) + 0.05:
            raise RuntimeError(f"Candidate {candidate_id} treatment exceeds its source duration.")

        render_settings = {
            **treatment.to_dict(),
            "source_start": source_start,
            "source_duration": source_duration,
            "target_duration": target_duration,
            "playback_rate": playback_rate,
            "audio": True,
        }
        treatment_kind = "phone-treated-360p-av-v1-" + hashlib.sha256(
            json.dumps(render_settings, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        clip_key = cache_key(source, source_start, source_duration, treatment_kind)
        clip = treated_cache / f"{position:02d}-{candidate_id:03d}-{clip_key}.mp4"
        print(
            f"[{position:02d}/{total}] Candidate {candidate_id:03d}: {item['treatment']}",
            flush=True,
        )
        clip_started = time.monotonic()
        was_cached = clip.exists() and clip.stat().st_size > 0
        render_treated_clip(
            source,
            clip,
            source_start,
            source_duration,
            playback_rate=playback_rate,
            stabilize=treatment.stabilize,
            crop_scale=treatment.crop_scale,
            contrast=treatment.contrast,
            saturation=treatment.saturation,
            motion_interpolation=treatment.motion_interpolation,
            rotate_counterclockwise=treatment.rotate_counterclockwise,
            zoom_strength=treatment.zoom_strength,
            zoom_center_x=treatment.zoom_center_x,
            zoom_center_y=treatment.zoom_center_y,
            include_audio=True,
            audio_playback_rate=treatment.audio_playback_rate,
            target_duration=target_duration,
            ffmpeg=str(FFMPEG),
            ffprobe=str(FFPROBE),
            timeout_seconds=1200,
        )
        clip_metadata = probe_video(clip, ffprobe=str(FFPROBE))
        elapsed = time.monotonic() - clip_started
        clips.append(clip)
        timings.append({
            "candidate_id": candidate_id,
            "elapsed_seconds": round(elapsed, 3),
            "output_duration": clip_metadata.duration,
            "cached": was_cached,
        })
        status_path.write_text(json.dumps({
            "state": "running",
            "render_id": render_id,
            "processed": position,
            "total": total,
            "current_candidate_id": candidate_id,
            "started_at": status_started_at,
            "updated_at": _now(),
        }, indent=2), encoding="utf-8")
        print(f"    ready in {elapsed:.1f}s · {clip_metadata.duration:.2f}s output", flush=True)

    print("Assembling the approved phone shots with source sound…", flush=True)
    concatenate_video_clips(clips, destination, ffmpeg=str(FFMPEG), timeout_seconds=300)
    output_metadata = probe_video(destination, ffprobe=str(FFPROBE))
    if not has_audio_stream(destination, ffprobe=str(FFPROBE)):
        raise RuntimeError("The phone rough cut was assembled without its audio track.")
    if abs(output_metadata.duration - VARIANT_SECONDS) > 0.25:
        raise RuntimeError(
            f"The assembled phone rough cut is {output_metadata.duration:.2f}s, not two minutes."
        )
    total_elapsed = time.monotonic() - started
    manifest = {
        "render_id": render_id,
        "project_id": PROJECT_ID,
        "variant_seconds": VARIANT_SECONDS,
        "created_at": _now(),
        "output": str(destination),
        "output_duration": output_metadata.duration,
        "output_size_bytes": output_metadata.size_bytes,
        "elapsed_seconds": round(total_elapsed, 3),
        "audio_included": True,
        "items": manifest_items,
        "timings": timings,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    status_path.write_text(json.dumps({
        "state": "complete",
        "render_id": render_id,
        "processed": total,
        "total": total,
        "output": str(destination),
        "duration": output_metadata.duration,
        "elapsed_seconds": round(total_elapsed, 3),
        "finished_at": _now(),
    }, indent=2), encoding="utf-8")
    print(f"OUTPUT={destination}", flush=True)
    print(f"MANIFEST={manifest_path}", flush=True)
    print(f"DURATION={output_metadata.duration:.3f}s", flush=True)
    print(f"ELAPSED={total_elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    main()
