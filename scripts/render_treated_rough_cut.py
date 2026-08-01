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
    probe_video,
    render_treated_clip,
)
from pyrenees_selects.server import build_application
from pyrenees_selects.treatment_plan import TREATED_ROUGH_CUT


PROJECT_ID = "pyrenees-2024"
VARIANT_SECONDS = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    started = time.monotonic()
    application = build_application()
    project = application.store.project(PROJECT_ID)
    if not project:
        raise RuntimeError("The Pyrenees project is not available.")
    items = application.store.storyboard_items(PROJECT_ID, VARIANT_SECONDS)
    approved = [item for item in items if item["review_state"] == "approved"]
    if len(approved) != len(items):
        raise RuntimeError("Complete the two-minute storyboard review before rendering treatments.")
    items_by_candidate = {int(item["candidate_id"]): item for item in approved}
    recipe_ids = [recipe.candidate_id for recipe in TREATED_ROUGH_CUT]
    if len(recipe_ids) != len(set(recipe_ids)):
        raise RuntimeError("The treated-cut recipe contains a duplicate candidate.")
    if set(recipe_ids) != set(items_by_candidate):
        raise RuntimeError("The treated-cut recipe does not match the approved storyboard.")

    manifest_items: list[dict[str, object]] = []
    for position, recipe in enumerate(TREATED_ROUGH_CUT, start=1):
        item = items_by_candidate[recipe.candidate_id]
        manifest_items.append({
            "position": position,
            **recipe.to_dict(),
            "filename": item["filename"],
            "original_note": item["note"],
            "storyboard_note": item["storyboard_note"],
        })
    manifest_seed = json.dumps(manifest_items, sort_keys=True, ensure_ascii=False).encode("utf-8")
    render_id = hashlib.sha256(manifest_seed).hexdigest()[:12]
    treated_cache = application.paths.cache / PROJECT_ID / "treated" / render_id
    exports = application.paths.root / "exports"
    destination = exports / f"Pyrenees-treated-rough-cut-{render_id}.mp4"
    manifest_path = exports / f"Pyrenees-treated-rough-cut-{render_id}.json"
    status_path = application.paths.root / "treated-rough-cut-status.json"
    treated_cache.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)

    clips: list[Path] = []
    timings: list[dict[str, object]] = []
    total = len(TREATED_ROUGH_CUT)
    for position, recipe in enumerate(TREATED_ROUGH_CUT, start=1):
        item = items_by_candidate[recipe.candidate_id]
        source = Path(item["path"]).resolve(strict=True)
        if source.parent != Path(project["source_dir"]).resolve(strict=True):
            raise RuntimeError(f"Candidate {recipe.candidate_id} is outside the project footage folder.")
        source_duration = float(item["source_duration"])
        if recipe.source_start + recipe.source_duration > source_duration + 0.05:
            raise RuntimeError(f"Candidate {recipe.candidate_id} treatment exceeds its source duration.")
        treatment_kind = "treated-360p-v1-" + hashlib.sha256(
            json.dumps(recipe.to_dict(), sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        clip_key = cache_key(
            source,
            recipe.source_start,
            recipe.source_duration,
            treatment_kind,
        )
        clip = treated_cache / f"{position:02d}-{recipe.candidate_id:03d}-{clip_key}.mp4"
        print(
            f"[{position:02d}/{total}] Candidate {recipe.candidate_id:03d}: {recipe.rationale}",
            flush=True,
        )
        clip_started = time.monotonic()
        was_cached = clip.exists() and clip.stat().st_size > 0
        render_treated_clip(
            source,
            clip,
            recipe.source_start,
            recipe.source_duration,
            playback_rate=recipe.playback_rate,
            stabilize=recipe.stabilize,
            crop_scale=recipe.crop_scale,
            contrast=recipe.contrast,
            motion_interpolation=recipe.motion_interpolation,
            timeout_seconds=900,
        )
        clip_metadata = probe_video(clip)
        elapsed = time.monotonic() - clip_started
        clips.append(clip)
        timings.append({
            "candidate_id": recipe.candidate_id,
            "elapsed_seconds": round(elapsed, 3),
            "output_duration": clip_metadata.duration,
            "cached": was_cached,
        })
        status_path.write_text(json.dumps({
            "state": "running",
            "render_id": render_id,
            "processed": position,
            "total": total,
            "current_candidate_id": recipe.candidate_id,
            "started_at": _now(),
            "updated_at": _now(),
        }, indent=2), encoding="utf-8")
        print(f"    ready in {elapsed:.1f}s · {clip_metadata.duration:.2f}s output", flush=True)

    print("Assembling the treated shots…", flush=True)
    concatenate_video_clips(clips, destination, timeout_seconds=300)
    output_metadata = probe_video(destination)
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
        "bird_included": False,
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
