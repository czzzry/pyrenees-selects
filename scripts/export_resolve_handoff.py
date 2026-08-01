#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyrenees_selects.media import probe_video
from pyrenees_selects.resolve_handoff import SourceMedia, build_fcpxml, write_handoff
from pyrenees_selects.server import build_application


PROJECT_ID = "pyrenees-2024"
HYBRID_RENDER_ID = "c203acd1249a"
FFPROBE = (ROOT / "build" / "media-tools" / "ffprobe").resolve()


def main() -> None:
    application = build_application()
    manifest_path = (
        application.paths.root
        / "exports"
        / f"Pyrenees-treated-hybrid-with-extended-bird-{HYBRID_RENDER_ID}.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest["items"]
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
    bird_path = (
        application.paths.root / "exports" / "Pyrenees-signature-bird-faithful-extended-2026-07-22.mp4"
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
    xml, handoff = build_fcpxml(items, sources, bird)
    handoff = {
        **handoff,
        "source_hybrid_manifest": str(manifest_path),
        "bird_original_source": str(sources[78].path),
        "media_policy": (
            "The XML and JSON contain no footage. Twenty-nine clips link to untouched 4K originals. "
            "The extended bird clip links to its approved 1080p master outside the repository. "
            "No video or generated media may be committed or pushed."
        ),
    }
    destination = Path.home() / "Desktop" / "Pyrenees Resolve Handoff"
    xml_path, json_path = write_handoff(destination, xml, handoff)
    print(f"FCPXML={xml_path}")
    print(f"MANIFEST={json_path}")
    print(f"ITEMS={handoff['item_count']}")
    print(f"DURATION={handoff['timeline_duration_seconds']:.3f}s")


if __name__ == "__main__":
    main()
