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
from pyrenees_selects.treatment_plan import (
    LONG_ROUGH_CUT_ADDITIONS,
    LONG_ROUGH_CUT_ORDER,
    TREATED_LONG_ROUGH_CUT,
    TREATED_ROUGH_CUT,
)


PROJECT_ID = "pyrenees-2024"
VARIANT_SECONDS = 180
NORTH_STAR_RENDER_ID = "9f88893e5b6c"
BIRD_DURATION = 7.96
FFMPEG = (ROOT / "build" / "media-tools" / "ffmpeg").resolve()
FFPROBE = (ROOT / "build" / "media-tools" / "ffprobe").resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _single_matching_clip(directory: Path, candidate_id: int) -> Path:
    matches = list(directory.glob(f"*-{candidate_id:03d}-*.mp4"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one cached North Star clip for candidate {candidate_id}, found {len(matches)}."
        )
    return matches[0].resolve(strict=True)


def main() -> None:
    started = time.monotonic()
    if not FFMPEG.is_file() or not FFPROBE.is_file():
        raise RuntimeError("The repository's bundled media tools are missing.")
    application = build_application()
    project = application.store.project(PROJECT_ID)
    if not project:
        raise RuntimeError("The Pyrenees project is not available.")
    storyboard = application.store.storyboard_items(PROJECT_ID, VARIANT_SECONDS)
    items_by_candidate = {int(item["candidate_id"]): item for item in storyboard}
    expected_storyboard = set(LONG_ROUGH_CUT_ORDER) - {78}
    if set(items_by_candidate) != expected_storyboard:
        raise RuntimeError("The three-minute storyboard no longer matches the longer-cut recipe.")

    bird_plan = application.store.edit_plan_item(78)
    if not bird_plan:
        raise RuntimeError("The signature bird plan is missing.")
    bird_clip = (
        application.paths.cache
        / PROJECT_ID
        / "signature"
        / "candidate-078-faithful-extended-360p.mp4"
    ).resolve(strict=True)
    bird_metadata = probe_video(bird_clip, ffprobe=str(FFPROBE))
    if abs(bird_metadata.duration - BIRD_DURATION) > 0.05:
        raise RuntimeError("The extended signature bird review clip has an unexpected duration.")

    base_recipes = {recipe.candidate_id: recipe for recipe in TREATED_ROUGH_CUT}
    addition_ids = {recipe.candidate_id for recipe in LONG_ROUGH_CUT_ADDITIONS}
    north_star_cache = application.paths.cache / PROJECT_ID / "treated" / NORTH_STAR_RENDER_ID
    if not north_star_cache.is_dir():
        raise RuntimeError("The completed North Star treatment cache is missing.")

    long_recipes = {recipe.candidate_id: recipe for recipe in TREATED_LONG_ROUGH_CUT}
    manifest_items: list[dict[str, object]] = []
    for position, candidate_id in enumerate(LONG_ROUGH_CUT_ORDER, start=1):
        if candidate_id == 78:
            manifest_items.append({
                "position": position,
                "candidate_id": 78,
                "signature_moment": True,
                "source_sections": [
                    {"start": 55.5, "duration": 3.4, "treatment": "stabilized wide flight over clouds"},
                    {"start": 59.2, "duration": 2.536, "treatment": "tracked mountain-backed wide-to-close push"},
                ],
                "output_duration": bird_metadata.duration,
                "filename": bird_plan["filename"],
                "original_note": bird_plan["note"],
                "rationale": "Extended signature bird encounter before the final cloud-sea ending.",
            })
            continue
        item = items_by_candidate[candidate_id]
        manifest_items.append({
            "position": position,
            **long_recipes[candidate_id].to_dict(),
            "filename": item["filename"],
            "original_note": item["note"],
            "storyboard_note": item["storyboard_note"],
            "reused_north_star_treatment": candidate_id in base_recipes,
        })

    manifest_seed = json.dumps(manifest_items, sort_keys=True, ensure_ascii=False).encode("utf-8")
    render_id = hashlib.sha256(manifest_seed).hexdigest()[:12]
    treated_cache = application.paths.cache / PROJECT_ID / "treated-long" / render_id
    exports = application.paths.root / "exports"
    destination = exports / f"Pyrenees-treated-long-rough-cut-with-extended-bird-{render_id}.mp4"
    manifest_path = exports / f"Pyrenees-treated-long-rough-cut-with-extended-bird-{render_id}.json"
    status_path = application.paths.root / "treated-long-rough-cut-status.json"
    treated_cache.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)

    clips_by_candidate: dict[int, Path] = {}
    timings: list[dict[str, object]] = []
    source_root = Path(project["source_dir"]).resolve(strict=True)
    total = len(TREATED_LONG_ROUGH_CUT)
    for index, recipe in enumerate(TREATED_LONG_ROUGH_CUT, start=1):
        candidate_id = recipe.candidate_id
        if candidate_id in base_recipes:
            clip = _single_matching_clip(north_star_cache, candidate_id)
            clips_by_candidate[candidate_id] = clip
            timings.append({
                "candidate_id": candidate_id,
                "elapsed_seconds": 0.0,
                "cached": True,
                "reused_north_star_treatment": True,
            })
            continue

        item = items_by_candidate[candidate_id]
        source = Path(item["path"]).resolve(strict=True)
        if source.parent != source_root:
            raise RuntimeError(f"Candidate {candidate_id} is outside the project footage folder.")
        if recipe.source_start + recipe.source_duration > float(item["source_duration"]) + 0.05:
            raise RuntimeError(f"Candidate {candidate_id} treatment exceeds its source duration.")
        treatment_kind = "treated-long-360p-v1-" + hashlib.sha256(
            json.dumps(recipe.to_dict(), sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        clip_key = cache_key(source, recipe.source_start, recipe.source_duration, treatment_kind)
        clip = treated_cache / f"{index:02d}-{candidate_id:03d}-{clip_key}.mp4"
        print(f"[{index:02d}/{total}] Candidate {candidate_id:03d}: {recipe.rationale}", flush=True)
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
            ffmpeg=str(FFMPEG),
            timeout_seconds=900,
        )
        elapsed = time.monotonic() - clip_started
        metadata = probe_video(clip, ffprobe=str(FFPROBE))
        clips_by_candidate[candidate_id] = clip
        timings.append({
            "candidate_id": candidate_id,
            "elapsed_seconds": round(elapsed, 3),
            "output_duration": metadata.duration,
            "cached": was_cached,
            "reused_north_star_treatment": False,
        })
        processed_additions = len([
            timing for timing in timings if not timing["reused_north_star_treatment"]
        ])
        status_path.write_text(json.dumps({
            "state": "running",
            "render_id": render_id,
            "processed_additions": processed_additions,
            "total_additions": len(addition_ids),
            "current_candidate_id": candidate_id,
            "updated_at": _now(),
        }, indent=2), encoding="utf-8")
        print(f"    ready in {elapsed:.1f}s · {metadata.duration:.2f}s output", flush=True)

    clips_by_candidate[78] = bird_clip
    clips = [clips_by_candidate[candidate_id] for candidate_id in LONG_ROUGH_CUT_ORDER]
    print("Assembling the longer cut…", flush=True)
    concatenate_video_clips(clips, destination, ffmpeg=str(FFMPEG), timeout_seconds=300)
    output_metadata = probe_video(destination, ffprobe=str(FFPROBE))
    elapsed = time.monotonic() - started
    manifest = {
        "render_id": render_id,
        "project_id": PROJECT_ID,
        "variant_seconds": VARIANT_SECONDS,
        "created_at": _now(),
        "output": str(destination),
        "output_duration": output_metadata.duration,
        "output_size_bytes": output_metadata.size_bytes,
        "elapsed_seconds": round(elapsed, 3),
        "bird_included": True,
        "bird_variant": "extended",
        "reused_north_star_segments": len(base_recipes),
        "newly_rendered_segments": len(addition_ids),
        "items": manifest_items,
        "timings": timings,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    status_path.write_text(json.dumps({
        "state": "complete",
        "render_id": render_id,
        "output": str(destination),
        "duration": output_metadata.duration,
        "elapsed_seconds": round(elapsed, 3),
        "finished_at": _now(),
    }, indent=2), encoding="utf-8")
    print(f"OUTPUT={destination}", flush=True)
    print(f"MANIFEST={manifest_path}", flush=True)
    print(f"DURATION={output_metadata.duration:.3f}s", flush=True)
    print(f"ELAPSED={elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    main()
