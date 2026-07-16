from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


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
    decision TEXT NOT NULL DEFAULT 'pending' CHECK(decision IN ('pending','keep','maybe','skip')),
    story_role TEXT CHECK(story_role IS NULL OR story_role IN ('opening','transition','peak','ending')),
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS media_project_capture_idx ON media(project_id, captured_at);
CREATE INDEX IF NOT EXISTS candidate_decision_idx ON candidates(decision, id);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, database: Path):
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)

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
        }

    def candidate(self, candidate_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT c.*,m.project_id,m.path,m.filename,m.captured_at,m.width,m.height,m.fps,m.codec,m.size_bytes,
                          m.duration source_duration
                   FROM candidates c JOIN media m ON m.id=c.media_id WHERE c.id=?""",
                (candidate_id,),
            ).fetchone()
        return dict(row) if row else None

    def next_candidate(self, project_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT c.*,m.project_id,m.path,m.filename,m.captured_at,m.width,m.height,m.fps,m.codec,m.size_bytes,
                          m.duration source_duration
                   FROM candidates c JOIN media m ON m.id=c.media_id
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
        return self.candidate(candidate_id) or {}
