from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .edit_plan import EDIT_PLAN_ITEMS, STORYBOARD_VARIANTS


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_dir TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    duration REAL NOT NULL CHECK(duration > 0),
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    fps REAL NOT NULL,
    codec TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    UNIQUE(project_id, path)
);
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER NOT NULL UNIQUE REFERENCES media(id) ON DELETE CASCADE,
    start_seconds REAL NOT NULL,
    duration REAL NOT NULL CHECK(duration > 0),
    handle_seconds REAL NOT NULL DEFAULT 3,
    chapter TEXT NOT NULL,
    reason TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    analysis_version INTEGER NOT NULL DEFAULT 0,
    decision TEXT NOT NULL DEFAULT 'pending' CHECK(decision IN ('pending','keep','maybe','skip')),
    story_role TEXT CHECK(story_role IS NULL OR story_role IN ('opening','transition','peak','ending')),
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS media_project_capture_idx ON media(project_id, captured_at);
CREATE INDEX IF NOT EXISTS candidate_decision_idx ON candidates(decision, id);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS screening_outcomes (
    candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK(decision IN ('keep','maybe','skip')),
    story_role TEXT CHECK(story_role IS NULL OR story_role IN ('opening','transition','peak','ending')),
    finalized_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_refinements (
    candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
    note TEXT NOT NULL DEFAULT '',
    note_anchor_seconds REAL,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edit_plan_items (
    candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
    recommendation TEXT NOT NULL CHECK(recommendation IN ('core','alternate','drop','deferred')),
    proposed_start_seconds REAL NOT NULL CHECK(proposed_start_seconds >= 0),
    proposed_duration REAL NOT NULL CHECK(proposed_duration > 0),
    treatment TEXT NOT NULL,
    story_group TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS storyboard_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    variant_seconds INTEGER NOT NULL CHECK(variant_seconds IN (90,120,180)),
    position INTEGER NOT NULL CHECK(position > 0),
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    target_duration REAL NOT NULL CHECK(target_duration > 0),
    review_state TEXT NOT NULL DEFAULT 'pending' CHECK(review_state IN ('pending','approved','removed')),
    replacement_candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL,
    storyboard_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id,variant_seconds,position)
);
CREATE INDEX IF NOT EXISTS storyboard_project_variant_idx ON storyboard_items(project_id,variant_seconds,position);
CREATE TABLE IF NOT EXISTS hybrid_reviews (
    storyboard_item_id INTEGER PRIMARY KEY REFERENCES storyboard_items(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK(decision IN ('add','long_only','unsure')),
    updated_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, database: Path):
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(candidates)").fetchall()}
            if "analysis_version" not in columns:
                connection.execute("ALTER TABLE candidates ADD COLUMN analysis_version INTEGER NOT NULL DEFAULT 0")
            storyboard_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(storyboard_items)").fetchall()
            }
            if "storyboard_note" not in storyboard_columns:
                connection.execute("ALTER TABLE storyboard_items ADD COLUMN storyboard_note TEXT NOT NULL DEFAULT ''")
            self._snapshot_completed_screenings(connection)
            self._seed_pyrenees_edit_plan(connection)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def upsert_project(self, project_id: str, name: str, source_dir: str) -> dict[str, Any]:
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO projects(id,name,source_dir,created_at,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, source_dir=excluded.source_dir, updated_at=excluded.updated_at""",
                (project_id, name, source_dir, now, now),
            )
        return self.project(project_id) or {}

    def project(self, project_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

    def projects(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def setting(self, key: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO app_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def replace_media(self, project_id: str, media_items: list[dict[str, Any]]) -> None:
        with self.connection() as connection:
            existing = {
                row["path"]: row
                for row in connection.execute("SELECT id,path FROM media WHERE project_id = ?", (project_id,)).fetchall()
            }
            incoming_paths = {str(item["path"]) for item in media_items}
            for path, row in existing.items():
                if path not in incoming_paths:
                    connection.execute("DELETE FROM media WHERE id = ?", (row["id"],))
            for item in media_items:
                connection.execute(
                    """INSERT INTO media(project_id,path,filename,captured_at,duration,width,height,fps,codec,size_bytes)
                       VALUES(?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(project_id,path) DO UPDATE SET
                         filename=excluded.filename, captured_at=excluded.captured_at, duration=excluded.duration,
                         width=excluded.width, height=excluded.height, fps=excluded.fps, codec=excluded.codec,
                         size_bytes=excluded.size_bytes""",
                    (
                        project_id, item["path"], item["filename"], item["captured_at"], item["duration"],
                        item["width"], item["height"], item["fps"], item["codec"], item["size_bytes"],
                    ),
                )

    def ensure_candidates(self, project_id: str, candidate_factory: Any) -> None:
        with self.connection() as connection:
            media_rows = connection.execute(
                "SELECT * FROM media WHERE project_id = ? ORDER BY captured_at, filename", (project_id,)
            ).fetchall()
            total = len(media_rows)
            for index, media_row in enumerate(media_rows):
                existing = connection.execute("SELECT id FROM candidates WHERE media_id = ?", (media_row["id"],)).fetchone()
                if existing:
                    continue
                candidate = candidate_factory(dict(media_row), index, total)
                connection.execute(
                    """INSERT INTO candidates(media_id,start_seconds,duration,handle_seconds,chapter,reason,score,updated_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        media_row["id"], candidate["start_seconds"], candidate["duration"], candidate["handle_seconds"],
                        candidate["chapter"], candidate["reason"], candidate["score"], utc_now(),
                    ),
                )

    def project_candidates(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT c.*,m.project_id,m.path,m.filename,m.captured_at,m.width,m.height,m.fps,m.codec,m.size_bytes,
                          m.duration source_duration,COALESCE(r.note,'') note,
                          r.note_anchor_seconds,r.reviewed_at,r.updated_at refinement_updated_at
                   FROM candidates c
                   JOIN media m ON m.id=c.media_id
                   LEFT JOIN candidate_refinements r ON r.candidate_id=c.id
                   WHERE m.project_id=? ORDER BY m.captured_at,c.id""",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_candidate_analysis(
        self,
        candidate_id: int,
        start_seconds: float,
        duration: float,
        reason: str,
        score: float,
        analysis_version: int,
    ) -> None:
        with self.connection() as connection:
            result = connection.execute(
                """UPDATE candidates
                   SET start_seconds=?, duration=?, reason=?, score=?, analysis_version=?, updated_at=?
                   WHERE id=? AND decision='pending'""",
                (start_seconds, duration, reason, score, analysis_version, utc_now(), candidate_id),
            )
            if result.rowcount not in {0, 1}:
                raise RuntimeError("Could not update analyzed candidate.")

    def _snapshot_completed_screenings(
        self,
        connection: sqlite3.Connection,
        project_id: str | None = None,
    ) -> None:
        parameters: tuple[Any, ...] = ()
        project_filter = ""
        if project_id is not None:
            project_filter = "AND m.project_id = ?"
            parameters = (project_id,)
        connection.execute(
            f"""INSERT OR IGNORE INTO screening_outcomes(candidate_id,decision,story_role,finalized_at)
                SELECT c.id,c.decision,c.story_role,?
                FROM candidates c JOIN media m ON m.id=c.media_id
                WHERE c.decision IN ('keep','maybe','skip') {project_filter}
                  AND NOT EXISTS (
                    SELECT 1 FROM candidates pending
                    JOIN media pending_media ON pending_media.id=pending.media_id
                    WHERE pending_media.project_id=m.project_id AND pending.decision='pending'
                  )""",
            (utc_now(), *parameters),
        )

    def _seed_pyrenees_edit_plan(self, connection: sqlite3.Connection) -> None:
        candidate_ids = tuple(EDIT_PLAN_ITEMS)
        placeholders = ",".join("?" for _ in candidate_ids)
        rows = connection.execute(
            f"""SELECT c.id,m.project_id FROM candidates c JOIN media m ON m.id=c.media_id
                WHERE c.id IN ({placeholders}) AND m.project_id='pyrenees-2024'""",
            candidate_ids,
        ).fetchall()
        if len(rows) != len(candidate_ids):
            return
        now = utc_now()
        for candidate_id, item in EDIT_PLAN_ITEMS.items():
            connection.execute(
                """INSERT OR IGNORE INTO edit_plan_items(
                       candidate_id,recommendation,proposed_start_seconds,proposed_duration,
                       treatment,story_group,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    candidate_id, item["recommendation"], item["start"], item["duration"],
                    item["treatment"], item["group"], now, now,
                ),
            )
        for variant_seconds, items in STORYBOARD_VARIANTS.items():
            for position, (candidate_id, target_duration) in enumerate(items, start=1):
                connection.execute(
                    """INSERT OR IGNORE INTO storyboard_items(
                           project_id,variant_seconds,position,candidate_id,target_duration,created_at,updated_at
                       ) VALUES('pyrenees-2024',?,?,?,?,?,?)""",
                    (variant_seconds, position, candidate_id, target_duration, now, now),
                )

    def summary(self, project_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            media = connection.execute(
                "SELECT COUNT(*) count, COALESCE(SUM(duration),0) duration, COALESCE(SUM(size_bytes),0) size_bytes FROM media WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            decisions = connection.execute(
                """SELECT c.decision, COUNT(*) count, COALESCE(SUM(c.duration),0) duration
                   FROM candidates c JOIN media m ON m.id=c.media_id WHERE m.project_id=? GROUP BY c.decision""",
                (project_id,),
            ).fetchall()
        decision_map = {row["decision"]: {"count": row["count"], "duration": row["duration"]} for row in decisions}
        return {
            "media_count": media["count"], "source_duration": media["duration"], "source_size_bytes": media["size_bytes"],
            "decisions": {key: decision_map.get(key, {"count": 0, "duration": 0}) for key in ("pending", "keep", "maybe", "skip")},
            "analyzed_count": self._analyzed_count(project_id),
        }

    def _analyzed_count(self, project_id: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT COUNT(*) count FROM candidates c JOIN media m ON m.id=c.media_id
                   WHERE m.project_id=? AND c.analysis_version > 0""",
                (project_id,),
            ).fetchone()
        return int(row["count"])

    def candidate(self, candidate_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT c.*,m.project_id,m.path,m.filename,m.captured_at,m.width,m.height,m.fps,m.codec,m.size_bytes,
                          m.duration source_duration,COALESCE(r.note,'') note,
                          r.note_anchor_seconds,r.reviewed_at,r.updated_at refinement_updated_at
                   FROM candidates c
                   JOIN media m ON m.id=c.media_id
                   LEFT JOIN candidate_refinements r ON r.candidate_id=c.id
                   WHERE c.id=?""",
                (candidate_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_candidate_note(self, candidate_id: int, note: str) -> dict[str, Any]:
        clean_note = note.strip()
        if len(clean_note) > 4_000:
            raise ValueError("Comments must be 4,000 characters or fewer.")
        now = utc_now()
        with self.connection() as connection:
            candidate = connection.execute(
                "SELECT id FROM candidates WHERE id=?",
                (candidate_id,),
            ).fetchone()
            if not candidate:
                raise KeyError(candidate_id)
            existing = connection.execute(
                "SELECT created_at FROM candidate_refinements WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            created_at = str(existing["created_at"]) if existing else now
            connection.execute(
                """INSERT INTO candidate_refinements(candidate_id,note,note_anchor_seconds,reviewed_at,created_at,updated_at)
                   VALUES(?,?,NULL,NULL,?,?)
                   ON CONFLICT(candidate_id) DO UPDATE SET
                     note=excluded.note,
                     updated_at=excluded.updated_at""",
                (candidate_id, clean_note, created_at, now),
            )
        saved = self.candidate(candidate_id)
        if not saved:
            raise KeyError(candidate_id)
        return saved

    def refinement_candidates(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT c.*,m.project_id,m.path,m.filename,m.captured_at,m.width,m.height,m.fps,m.codec,m.size_bytes,
                          m.duration source_duration,o.decision screening_decision,o.story_role screening_story_role,
                          r.note,r.note_anchor_seconds,r.reviewed_at,r.updated_at refinement_updated_at
                   FROM screening_outcomes o
                   JOIN candidates c ON c.id=o.candidate_id
                   JOIN media m ON m.id=c.media_id
                   LEFT JOIN candidate_refinements r ON r.candidate_id=c.id
                   WHERE m.project_id=? AND o.decision IN ('keep','maybe')
                   ORDER BY m.captured_at,c.id""",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def refinement_summary(self, project_id: str) -> dict[str, int]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT COUNT(*) total,
                          COALESCE(SUM(CASE WHEN r.reviewed_at IS NOT NULL THEN 1 ELSE 0 END),0) reviewed,
                          COALESCE(SUM(CASE WHEN LENGTH(TRIM(COALESCE(r.note,''))) > 0 THEN 1 ELSE 0 END),0) noted
                   FROM screening_outcomes o
                   JOIN candidates c ON c.id=o.candidate_id
                   JOIN media m ON m.id=c.media_id
                   LEFT JOIN candidate_refinements r ON r.candidate_id=c.id
                   WHERE m.project_id=? AND o.decision IN ('keep','maybe')""",
                (project_id,),
            ).fetchone()
        return {"total": int(row["total"]), "reviewed": int(row["reviewed"]), "noted": int(row["noted"])}

    def save_refinement(
        self,
        candidate_id: int,
        note: str,
        note_anchor_seconds: float | None = None,
        reviewed: bool = False,
    ) -> dict[str, Any]:
        clean_note = note.strip()
        if len(clean_note) > 4_000:
            raise ValueError("Notes must be 4,000 characters or fewer.")
        now = utc_now()
        with self.connection() as connection:
            candidate = connection.execute(
                """SELECT c.id,m.duration source_duration,o.decision
                   FROM candidates c
                   JOIN media m ON m.id=c.media_id
                   JOIN screening_outcomes o ON o.candidate_id=c.id
                   WHERE c.id=? AND o.decision IN ('keep','maybe')""",
                (candidate_id,),
            ).fetchone()
            if not candidate:
                raise KeyError(candidate_id)
            if note_anchor_seconds is not None:
                note_anchor_seconds = float(note_anchor_seconds)
                if not 0 <= note_anchor_seconds <= float(candidate["source_duration"]):
                    raise ValueError("The note timestamp is outside the source clip.")
            existing = connection.execute(
                "SELECT created_at,reviewed_at FROM candidate_refinements WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            created_at = str(existing["created_at"]) if existing else now
            reviewed_at = str(existing["reviewed_at"]) if existing and existing["reviewed_at"] else None
            if reviewed and not reviewed_at:
                reviewed_at = now
            connection.execute(
                """INSERT INTO candidate_refinements(candidate_id,note,note_anchor_seconds,reviewed_at,created_at,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(candidate_id) DO UPDATE SET
                     note=excluded.note,
                     note_anchor_seconds=excluded.note_anchor_seconds,
                     reviewed_at=excluded.reviewed_at,
                     updated_at=excluded.updated_at""",
                (candidate_id, clean_note, note_anchor_seconds, reviewed_at, created_at, now),
            )
            project_row = connection.execute(
                "SELECT m.project_id FROM candidates c JOIN media m ON m.id=c.media_id WHERE c.id=?",
                (candidate_id,),
            ).fetchone()
        return next(
            candidate for candidate in self.refinement_candidates(str(project_row["project_id"]))
            if int(candidate["id"]) == candidate_id
        )

    def edit_plan_item(self, candidate_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT p.*,c.start_seconds original_start_seconds,c.duration original_duration,
                          m.project_id,m.path,m.filename,m.captured_at,m.duration source_duration,
                          m.width,m.height,m.fps,m.codec,m.size_bytes,o.decision screening_decision,
                          COALESCE(r.note,'') note
                   FROM edit_plan_items p
                   JOIN candidates c ON c.id=p.candidate_id
                   JOIN media m ON m.id=c.media_id
                   JOIN screening_outcomes o ON o.candidate_id=c.id
                   LEFT JOIN candidate_refinements r ON r.candidate_id=c.id
                   WHERE p.candidate_id=?""",
                (candidate_id,),
            ).fetchone()
        return dict(row) if row else None

    def storyboard_items(self, project_id: str, variant_seconds: int = 120) -> list[dict[str, Any]]:
        if variant_seconds not in STORYBOARD_VARIANTS:
            raise ValueError("Choose the 90-second, two-minute, or three-minute storyboard.")
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT s.id storyboard_item_id,s.variant_seconds,s.position,s.candidate_id planned_candidate_id,
                          s.target_duration,s.review_state,s.replacement_candidate_id,s.storyboard_note,
                          c.id candidate_id,c.start_seconds original_start_seconds,c.duration original_duration,
                          c.chapter,c.reason,c.score,m.project_id,m.path,m.filename,m.captured_at,
                          m.duration source_duration,m.width,m.height,m.fps,m.codec,m.size_bytes,
                          o.decision screening_decision,COALESCE(r.note,'') note,
                          p.recommendation,p.proposed_start_seconds,p.proposed_duration,p.treatment,p.story_group
                   FROM storyboard_items s
                   JOIN candidates c ON c.id=COALESCE(s.replacement_candidate_id,s.candidate_id)
                   JOIN media m ON m.id=c.media_id
                   JOIN screening_outcomes o ON o.candidate_id=c.id
                   JOIN edit_plan_items p ON p.candidate_id=c.id
                   LEFT JOIN candidate_refinements r ON r.candidate_id=c.id
                   WHERE s.project_id=? AND s.variant_seconds=?
                   ORDER BY s.position""",
                (project_id, variant_seconds),
            ).fetchall()
        return [dict(row) for row in rows]

    def storyboard_alternatives(self, project_id: str, variant_seconds: int = 120) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT p.*,c.start_seconds original_start_seconds,c.duration original_duration,
                          c.chapter,c.reason,m.filename,m.captured_at,m.duration source_duration,
                          m.width,m.height,m.fps,m.codec,o.decision screening_decision,
                          COALESCE(r.note,'') note
                   FROM edit_plan_items p
                   JOIN candidates c ON c.id=p.candidate_id
                   JOIN media m ON m.id=c.media_id
                   JOIN screening_outcomes o ON o.candidate_id=c.id
                   LEFT JOIN candidate_refinements r ON r.candidate_id=c.id
                   WHERE m.project_id=? AND p.recommendation='alternate'
                     AND p.candidate_id NOT IN (
                       SELECT COALESCE(replacement_candidate_id,candidate_id)
                       FROM storyboard_items WHERE project_id=? AND variant_seconds=? AND review_state<>'removed'
                     )
                   ORDER BY m.captured_at,c.id""",
                (project_id, project_id, variant_seconds),
            ).fetchall()
        return [dict(row) for row in rows]

    def storyboard_summary(self, project_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT variant_seconds,COUNT(*) total,
                          SUM(CASE WHEN review_state='pending' THEN 1 ELSE 0 END) pending,
                          SUM(CASE WHEN review_state='approved' THEN 1 ELSE 0 END) approved,
                          SUM(CASE WHEN review_state='removed' THEN 1 ELSE 0 END) removed,
                          COALESCE(SUM(CASE WHEN review_state<>'removed' THEN target_duration ELSE 0 END),0) target_duration
                   FROM storyboard_items WHERE project_id=? GROUP BY variant_seconds ORDER BY variant_seconds""",
                (project_id,),
            ).fetchall()
        return {
            str(row["variant_seconds"]): {
                "total": int(row["total"]), "pending": int(row["pending"]),
                "approved": int(row["approved"]), "removed": int(row["removed"]),
                "target_duration": float(row["target_duration"]),
            }
            for row in rows
        }

    def hybrid_review_items(self, project_id: str, candidate_ids: tuple[int, ...]) -> list[dict[str, Any]]:
        storyboard = self.storyboard_items(project_id, 180)
        by_candidate = {int(item["candidate_id"]): item for item in storyboard}
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT h.storyboard_item_id,h.decision
                   FROM hybrid_reviews h
                   JOIN storyboard_items s ON s.id=h.storyboard_item_id
                   WHERE s.project_id=? AND s.variant_seconds=180""",
                (project_id,),
            ).fetchall()
        decisions = {int(row["storyboard_item_id"]): str(row["decision"]) for row in rows}
        return [
            {
                **by_candidate[candidate_id],
                "hybrid_decision": decisions.get(int(by_candidate[candidate_id]["storyboard_item_id"]), "pending"),
            }
            for candidate_id in candidate_ids
            if candidate_id in by_candidate
        ]

    def hybrid_review_summary(self, project_id: str, candidate_ids: tuple[int, ...]) -> dict[str, int]:
        items = self.hybrid_review_items(project_id, candidate_ids)
        counts = {"pending": 0, "add": 0, "long_only": 0, "unsure": 0}
        for item in items:
            counts[str(item["hybrid_decision"])] += 1
        return {"total": len(items), **counts}

    def save_hybrid_review(self, storyboard_item_id: int, decision: str) -> dict[str, Any]:
        if decision not in {"add", "long_only", "unsure"}:
            raise ValueError("Choose Add to hybrid, Long version only, or Unsure.")
        now = utc_now()
        with self.connection() as connection:
            item = connection.execute(
                "SELECT project_id,variant_seconds,candidate_id FROM storyboard_items WHERE id=?",
                (storyboard_item_id,),
            ).fetchone()
            if not item or int(item["variant_seconds"]) != 180:
                raise KeyError(storyboard_item_id)
            connection.execute(
                """INSERT INTO hybrid_reviews(storyboard_item_id,decision,updated_at)
                   VALUES(?,?,?)
                   ON CONFLICT(storyboard_item_id) DO UPDATE SET
                     decision=excluded.decision,updated_at=excluded.updated_at""",
                (storyboard_item_id, decision, now),
            )
        return {
            "storyboard_item_id": storyboard_item_id,
            "candidate_id": int(item["candidate_id"]),
            "project_id": str(item["project_id"]),
            "decision": decision,
            "updated_at": now,
        }

    def review_storyboard_item(
        self,
        storyboard_item_id: int,
        decision: str,
        replacement_candidate_id: int | None = None,
    ) -> None:
        if decision not in {"approve", "remove", "replace", "restore"}:
            raise ValueError("Choose Approve, Remove, Replace, or Restore.")
        with self.connection() as connection:
            item = connection.execute(
                """SELECT s.*,p.story_group FROM storyboard_items s
                   JOIN edit_plan_items p ON p.candidate_id=s.candidate_id WHERE s.id=?""",
                (storyboard_item_id,),
            ).fetchone()
            if not item:
                raise KeyError(storyboard_item_id)
            review_state = "removed" if decision == "remove" else "approved"
            replacement: int | None = (
                int(item["replacement_candidate_id"])
                if decision == "approve" and item["replacement_candidate_id"] is not None
                else None
            )
            if decision == "replace":
                if replacement_candidate_id is None:
                    raise ValueError("Choose an alternate shot first.")
                alternate = connection.execute(
                    """SELECT p.story_group,p.recommendation,m.project_id FROM edit_plan_items p
                       JOIN candidates c ON c.id=p.candidate_id JOIN media m ON m.id=c.media_id
                       WHERE p.candidate_id=?""",
                    (replacement_candidate_id,),
                ).fetchone()
                if (
                    not alternate
                    or alternate["project_id"] != item["project_id"]
                    or alternate["story_group"] != item["story_group"]
                    or alternate["recommendation"] != "alternate"
                ):
                    raise ValueError("Choose an alternate from the same part of the journey.")
                duplicate = connection.execute(
                    """SELECT 1 FROM storyboard_items WHERE project_id=? AND variant_seconds=? AND id<>?
                       AND review_state<>'removed' AND COALESCE(replacement_candidate_id,candidate_id)=?""",
                    (item["project_id"], item["variant_seconds"], storyboard_item_id, replacement_candidate_id),
                ).fetchone()
                if duplicate:
                    raise ValueError("That alternate is already used in this storyboard.")
                replacement = replacement_candidate_id
            connection.execute(
                """UPDATE storyboard_items SET review_state=?,replacement_candidate_id=?,updated_at=? WHERE id=?""",
                (review_state, replacement, utc_now(), storyboard_item_id),
            )

    def save_storyboard_note(self, storyboard_item_id: int, note: str) -> dict[str, Any]:
        clean_note = note.strip()
        if len(clean_note) > 4_000:
            raise ValueError("Notes must be 4,000 characters or fewer.")
        now = utc_now()
        with self.connection() as connection:
            result = connection.execute(
                "UPDATE storyboard_items SET storyboard_note=?,updated_at=? WHERE id=?",
                (clean_note, now, storyboard_item_id),
            )
            if result.rowcount != 1:
                raise KeyError(storyboard_item_id)
        return {
            "storyboard_item_id": storyboard_item_id,
            "storyboard_note": clean_note,
            "updated_at": now,
        }

    def next_candidate(self, project_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT c.*,m.project_id,m.path,m.filename,m.captured_at,m.width,m.height,m.fps,m.codec,m.size_bytes,
                          m.duration source_duration,COALESCE(r.note,'') note,
                          r.note_anchor_seconds,r.reviewed_at,r.updated_at refinement_updated_at
                   FROM candidates c
                   JOIN media m ON m.id=c.media_id
                   LEFT JOIN candidate_refinements r ON r.candidate_id=c.id
                   WHERE m.project_id=? AND c.decision='pending' ORDER BY m.captured_at,c.id LIMIT 1""",
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def decide(self, candidate_id: int, decision: str, story_role: str | None = None) -> dict[str, Any]:
        if decision not in {"pending", "keep", "maybe", "skip"}:
            raise ValueError("invalid decision")
        if story_role not in {None, "opening", "transition", "peak", "ending"}:
            raise ValueError("invalid story role")
        with self.connection() as connection:
            result = connection.execute(
                "UPDATE candidates SET decision=?, story_role=?, updated_at=? WHERE id=?",
                (decision, story_role, utc_now(), candidate_id),
            )
            if result.rowcount != 1:
                raise KeyError(candidate_id)
            project_row = connection.execute(
                "SELECT m.project_id FROM candidates c JOIN media m ON m.id=c.media_id WHERE c.id=?",
                (candidate_id,),
            ).fetchone()
            self._snapshot_completed_screenings(connection, str(project_row["project_id"]))
        return self.candidate(candidate_id) or {}
