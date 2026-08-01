#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyrenees_selects.media import probe_video
from pyrenees_selects.resolve_handoff import SourceMedia, build_fcpxml, write_handoff
from pyrenees_selects.server import build_application


DRONE_RENDER_ID = "c203acd1249a"
PHONE_RENDER_ID = "8ebdb64e7215"
INTEGRATED_RENDER_ID = "7a77c085f26e"
FFPROBE = (ROOT / "build" / "media-tools" / "ffprobe").resolve()

WILDLIFE_FINISH_NOTES = {
    102: (
        "Sky bird is credible only around the clearest early frames. Use the balanced AI treatment "
        "briefly, track the silhouette, and reject any frame whose wing shape changes."
    ),
    113: (
        "Track and reframe the ram from the native 4K source. Use stronger AI on the ram only, "
        "preserve the faithful forest background, and verify the horn outline frame by frame."
    ),
    119: (
        "The deer is clearest near 00:03.55–00:03.75. Keep this moment shorter than eight seconds "
        "if optical flow smears the head or body; enhance the deer only, not the branches."
    ),
    78: (
        "Balanced AI passed the three-frame motion-consistency test. Reuse the approved tracked "
        "vulture master and isolate stronger enhancement to the bird while preserving the clouds."
    ),
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_items(
    integrated: dict[str, Any],
    drone: dict[str, Any],
    phone: dict[str, Any],
) -> list[dict[str, Any]]:
    drone_by_id = {int(item["candidate_id"]): item for item in drone["items"]}
    phone_by_id = {int(item["candidate_id"]): item for item in phone["items"]}
    normalized: list[dict[str, Any]] = []
    for integrated_item in integrated["items"]:
        candidate_id = int(integrated_item["candidate_id"])
        origin = str(integrated_item["origin"])
        if origin == "drone":
            item = dict(drone_by_id[candidate_id])
            item["origin"] = origin
        elif origin == "phone":
            source = phone_by_id[candidate_id]
            item = {
                **source,
                "origin": origin,
                "output_duration": float(source["target_duration"]),
                "rationale": source["treatment_note"],
                "original_note": source["owner_comment"],
                "hybrid_note": "",
            }
        else:
            raise ValueError(f"Unknown integrated origin: {origin}")
        item["position"] = int(integrated_item["position"])
        if candidate_id in WILDLIFE_FINISH_NOTES:
            item["finish_note"] = WILDLIFE_FINISH_NOTES[candidate_id]
        normalized.append(item)
    return normalized


def main() -> None:
    application = build_application()
    exports = application.paths.root / "exports"
    integrated_path = exports / (
        f"Pyrenees-combined-drone-phone-rough-cut-{INTEGRATED_RENDER_ID}.json"
    )
    drone_path = exports / (
        f"Pyrenees-treated-hybrid-with-extended-bird-{DRONE_RENDER_ID}.json"
    )
    phone_path = exports / f"Pyrenees-phone-treated-rough-cut-{PHONE_RENDER_ID}.json"
    integrated = _read_json(integrated_path)
    drone = _read_json(drone_path)
    phone = _read_json(phone_path)
    items = _normalized_items(integrated, drone, phone)

    candidate_ids = [int(item["candidate_id"]) for item in items]
    placeholders = ",".join("?" for _ in candidate_ids)
    with application.store.connection() as connection:
        rows = connection.execute(
            f"""SELECT c.id AS candidate_id, m.path, m.duration, m.width, m.height, m.fps
                FROM candidates c
                JOIN media m ON m.id = c.media_id
                WHERE c.id IN ({placeholders})""",
            candidate_ids,
        ).fetchall()
    sources = {
        int(row["candidate_id"]): SourceMedia(
            candidate_id=int(row["candidate_id"]),
            path=Path(row["path"]).resolve(strict=True),
            duration=float(row["duration"]),
            width=int(row["width"]),
            height=int(row["height"]),
            fps=float(row["fps"]),
        )
        for row in rows
    }
    missing = set(candidate_ids) - set(sources)
    if missing:
        raise RuntimeError(f"Original media is missing for candidates: {sorted(missing)}")

    bird_path = (
        exports / "Pyrenees-signature-bird-faithful-extended-2026-07-22.mp4"
    ).resolve(strict=True)
    bird_video = probe_video(bird_path, ffprobe=str(FFPROBE))
    bird = SourceMedia(
        candidate_id=78,
        path=bird_path,
        duration=bird_video.duration,
        width=bird_video.width,
        height=bird_video.height,
        fps=30_000 / 1_001,
    )
    phone_ids = frozenset(
        int(item["candidate_id"]) for item in items if item["origin"] == "phone"
    )
    xml, handoff = build_fcpxml(
        items,
        sources,
        bird,
        timeline_name="Pyrenees Integrated Film · 5m25s · 4K Originals",
        expected_item_count=50,
        timeline_width=3_840,
        timeline_height=2_160,
        event_name="Pyrenees Integrated 4K Handoff",
        audio_candidate_ids=phone_ids,
        sequence_note=(
            "Fifty-shot chronological drone/phone film linked to native originals. Phone source "
            "audio is attached for selective use. Finish with a music spine, the train opening, "
            "selected owner comments, horse neigh, and cow-traffic-jam audio. Keep generic drone "
            "ambience subtle. Wildlife enhancement notes are attached to C78, C102, C113, and C119."
        ),
    )
    comparison = (
        exports / "Pyrenees-wildlife-AI-comparison-2026-07-23.jpg"
    ).resolve(strict=True)
    motion_test = (
        exports / "Pyrenees-vulture-AI-motion-consistency-2026-07-23.mp4"
    ).resolve(strict=True)
    handoff = {
        **handoff,
        "source_integrated_manifest": str(integrated_path),
        "source_drone_manifest": str(drone_path),
        "source_phone_manifest": str(phone_path),
        "wildlife_ai_still_comparison": str(comparison),
        "vulture_ai_motion_test": str(motion_test),
        "sound_plan": {
            "music": "Use one backing track as the film's spine.",
            "featured_source_audio": [
                "train at the start",
                "selected owner comments",
                "horse neigh",
                "cow traffic jam",
            ],
            "drone_ambience": "Use very subtle matching ambience only where it supports the cut.",
            "mix": "Duck music under featured phone audio in Fairlight.",
        },
        "media_policy": (
            "The FCPXML and JSON contain no footage. Forty-nine items link to native original "
            "media; candidate C78 links to the preserved tracked 1080p vulture master, with its "
            "untouched 4K source retained as the recovery reference."
        ),
    }
    destination = Path.home() / "Desktop" / "Pyrenees Combined Resolve Handoff"
    xml_path, json_path = write_handoff(
        destination,
        xml,
        handoff,
        stem="Pyrenees-Integrated-5m25s-4K-Resolve",
    )
    print(f"FCPXML={xml_path}")
    print(f"MANIFEST={json_path}")
    print(f"ITEMS={handoff['item_count']}")
    print(f"AUDIO_ITEMS={handoff['source_audio_item_count']}")
    print(f"DURATION={handoff['timeline_duration_seconds']:.3f}s")


if __name__ == "__main__":
    main()
