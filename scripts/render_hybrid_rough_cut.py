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

from pyrenees_selects.media import cache_key, concatenate_video_clips, probe_video, render_treated_clip
from pyrenees_selects.server import build_application
from pyrenees_selects.treatment_plan import (
    HYBRID_COMMENT_TREATMENTS,
    LONG_ROUGH_CUT_ADDITIONS,
    LONG_ROUGH_CUT_ORDER,
    TREATED_ROUGH_CUT,
)


PROJECT_ID = "pyrenees-2024"
NORTH_STAR_RENDER_ID = "9f88893e5b6c"
BIRD_DURATION = 7.96
FFMPEG = (ROOT / "build" / "media-tools" / "ffmpeg").resolve()
FFPROBE = (ROOT / "build" / "media-tools" / "ffprobe").resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _single_matching_clip(directory: Path, candidate_id: int) -> Path:
    matches = list(directory.glob(f"*-{candidate_id:03d}-*.mp4"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one cached clip for candidate {candidate_id}, found {len(matches)}.")
    return matches[0].resolve(strict=True)


def main() -> None:
    started = time.monotonic()
    if not FFMPEG.is_file() or not FFPROBE.is_file():
        raise RuntimeError("The repository's bundled media tools are missing.")

    application = build_application()
    project = application.store.project(PROJECT_ID)
    if not project:
        raise RuntimeError("The Pyrenees project is not available.")
    hybrid = application.hybrid_state(PROJECT_ID)
    if int(hybrid["summary"]["pending"]) != 0:
        raise RuntimeError("Finish all 13 hybrid choices before rendering.")

    items_by_candidate = {int(item["candidate_id"]): item for item in hybrid["items"]}
    selected_ids = {
        candidate_id for candidate_id, item in items_by_candidate.items()
        if item["hybrid_decision"] == "add"
    }
    if not selected_ids:
        raise RuntimeError("No longer-cut shots were selected for the hybrid.")

    base_recipes = {recipe.candidate_id: recipe for recipe in TREATED_ROUGH_CUT}
    addition_recipes = {recipe.candidate_id: recipe for recipe in LONG_ROUGH_CUT_ADDITIONS}
    comment_recipes = {recipe.candidate_id: recipe for recipe in HYBRID_COMMENT_TREATMENTS}
    unexpected_overrides = set(comment_recipes) - selected_ids
    if unexpected_overrides:
        raise RuntimeError(f"A comment treatment is no longer selected: {sorted(unexpected_overrides)}")

    order = tuple(
        candidate_id for candidate_id in LONG_ROUGH_CUT_ORDER
        if candidate_id in base_recipes or candidate_id == 78 or candidate_id in selected_ids
    )
    bird_plan = application.store.edit_plan_item(78)
    if not bird_plan:
        raise RuntimeError("The signature bird plan is missing.")
    bird_clip = (
        application.paths.cache / PROJECT_ID / "signature" / "candidate-078-faithful-extended-360p.mp4"
    ).resolve(strict=True)
    if abs(probe_video(bird_clip, ffprobe=str(FFPROBE)).duration - BIRD_DURATION) > 0.05:
        raise RuntimeError("The extended signature bird clip has an unexpected duration.")

    manifest_items: list[dict[str, object]] = []
    for position, candidate_id in enumerate(order, start=1):
        if candidate_id == 78:
            manifest_items.append({
                "position": position,
                "candidate_id": 78,
                "signature_moment": True,
                "output_duration": BIRD_DURATION,
                "filename": bird_plan["filename"],
                "rationale": "Extended signature bird encounter before the cloud-sea ending.",
            })
            continue
        if candidate_id in base_recipes:
            recipe = base_recipes[candidate_id]
            item = application.store.edit_plan_item(candidate_id)
            source_kind = "north_star"
        else:
            recipe = comment_recipes.get(candidate_id, addition_recipes[candidate_id])
            item = items_by_candidate[candidate_id]
            source_kind = "hybrid_refinement" if candidate_id in comment_recipes else "long_cut"
        if not item:
            raise RuntimeError(f"Candidate {candidate_id} is missing from the edit plan.")
        manifest_items.append({
            "position": position,
            **recipe.to_dict(),
            "filename": item["filename"],
            "original_note": item.get("note") or "",
            "hybrid_note": item.get("storyboard_note") or "",
            "source_kind": source_kind,
        })

    seed = json.dumps(manifest_items, sort_keys=True, ensure_ascii=False).encode("utf-8")
    render_id = hashlib.sha256(seed).hexdigest()[:12]
    cache = application.paths.cache / PROJECT_ID / "treated-hybrid" / render_id
    exports = application.paths.root / "exports"
    destination = exports / f"Pyrenees-treated-hybrid-with-extended-bird-{render_id}.mp4"
    manifest_path = exports / f"Pyrenees-treated-hybrid-with-extended-bird-{render_id}.json"
    status_path = application.paths.root / "treated-hybrid-status.json"
    cache.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)

    north_star_cache = application.paths.cache / PROJECT_ID / "treated" / NORTH_STAR_RENDER_ID
    source_root = Path(project["source_dir"]).resolve(strict=True)
    clips_by_candidate: dict[int, Path] = {}
    timings: list[dict[str, object]] = []
    for candidate_id in order:
        if candidate_id == 78:
            clips_by_candidate[candidate_id] = bird_clip
            continue
        if candidate_id in base_recipes:
            clips_by_candidate[candidate_id] = _single_matching_clip(north_star_cache, candidate_id)
            timings.append({"candidate_id": candidate_id, "elapsed_seconds": 0.0, "source_kind": "north_star"})
            continue
        if candidate_id not in comment_recipes:
            clips_by_candidate[candidate_id] = application.hybrid_asset(candidate_id)
            timings.append({"candidate_id": candidate_id, "elapsed_seconds": 0.0, "source_kind": "long_cut"})
            continue

        recipe = comment_recipes[candidate_id]
        item = items_by_candidate[candidate_id]
        source = Path(item["path"]).resolve(strict=True)
        if source.parent != source_root:
            raise RuntimeError(f"Candidate {candidate_id} is outside the project footage folder.")
        if recipe.source_start + recipe.source_duration > float(item["source_duration"]) + 0.05:
            raise RuntimeError(f"Candidate {candidate_id} treatment exceeds its source duration.")
        kind = "treated-hybrid-360p-v1-" + hashlib.sha256(
            json.dumps(recipe.to_dict(), sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        key = cache_key(source, recipe.source_start, recipe.source_duration, kind)
        clip = cache / f"{candidate_id:03d}-{key}.mp4"
        was_cached = clip.exists() and clip.stat().st_size > 0
        print(f"Candidate {candidate_id:03d}: {recipe.rationale}", flush=True)
        clip_started = time.monotonic()
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
            "source_kind": "hybrid_refinement",
        })
        status_path.write_text(json.dumps({
            "state": "running",
            "render_id": render_id,
            "current_candidate_id": candidate_id,
            "updated_at": _now(),
        }, indent=2), encoding="utf-8")
        print(f"    ready in {elapsed:.1f}s · {metadata.duration:.2f}s output", flush=True)

    clips = [clips_by_candidate[candidate_id] for candidate_id in order]
    print("Assembling the hybrid cut…", flush=True)
    concatenate_video_clips(clips, destination, ffmpeg=str(FFMPEG), timeout_seconds=300)
    metadata = probe_video(destination, ffprobe=str(FFPROBE))
    elapsed = time.monotonic() - started
    manifest = {
        "render_id": render_id,
        "project_id": PROJECT_ID,
        "created_at": _now(),
        "output": str(destination),
        "output_duration": metadata.duration,
        "output_size_bytes": metadata.size_bytes,
        "elapsed_seconds": round(elapsed, 3),
        "bird_included": True,
        "bird_variant": "extended",
        "selected_long_only_candidates": sorted(selected_ids),
        "excluded_long_only_candidates": sorted(set(addition_recipes) - selected_ids),
        "comment_refinements": sorted(comment_recipes),
        "items": manifest_items,
        "timings": timings,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    status_path.write_text(json.dumps({
        "state": "complete",
        "render_id": render_id,
        "output": str(destination),
        "duration": metadata.duration,
        "elapsed_seconds": round(elapsed, 3),
        "finished_at": _now(),
    }, indent=2), encoding="utf-8")
    print(f"OUTPUT={destination}", flush=True)
    print(f"MANIFEST={manifest_path}", flush=True)
    print(f"DURATION={metadata.duration:.3f}s", flush=True)
    print(f"ELAPSED={elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    main()
