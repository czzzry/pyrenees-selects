from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .media import VideoMetadata, candidate_range, probe_video, top_level_videos
from .store import Store


PROJECT_ID = "pyrenees-2024"


def _chapter(index: int, total: int) -> str:
    progress = index / max(1, total - 1)
    if progress < 0.16:
        return "Early journey"
    if progress < 0.36:
        return "First foothills"
    if progress < 0.70:
        return "High country"
    if progress < 0.90:
        return "Late mountains"
    return "Journey's end"


def baseline_candidate(media: dict[str, Any], index: int, total: int) -> dict[str, Any]:
    start, duration = candidate_range(float(media["duration"]))
    return {
        "start_seconds": start,
        "duration": duration,
        "handle_seconds": 3.0,
        "chapter": _chapter(index, total),
        "reason": "Shown to prove the complete screening workflow. Technical and visual ranking has not yet been applied.",
        "score": 0.0,
    }


def scan_project(
    store: Store,
    project_id: str,
    probe: Callable[[Path], VideoMetadata] = probe_video,
) -> dict[str, Any]:
    project = store.project(project_id)
    if not project:
        raise KeyError(project_id)
    source_dir = Path(project["source_dir"]).expanduser().resolve(strict=True)
    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for path in top_level_videos(source_dir):
        try:
            items.append(probe(path).to_dict())
        except Exception as exc:
            failures.append({"filename": path.name, "error": str(exc)})
    if not items:
        raise ValueError("No readable top-level video files were found in that folder.")
    store.replace_media(project_id, items)
    store.ensure_candidates(project_id, baseline_candidate)
    return {"summary": store.summary(project_id), "failures": failures}
