from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from .media import VIDEO_EXTENSIONS, VideoMetadata, probe_video


SCHEMA_VERSION = 2
DECISIONS = {"keep", "maybe", "skip"}
STORY_ROLES = {"opening", "transition", "peak", "ending"}
AUDIO_INTENTS = {"undecided", "mute", "preserve", "speech", "background"}
ORIENTATIONS = {"landscape", "portrait", "undecided"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class ProjectOptions:
    name: str
    target_duration: float | None = None
    orientation: str = "undecided"
    intent: str = ""
    ideal_clip_duration: float = 8.0


@dataclass(frozen=True)
class SelectionDraft:
    source_id: str
    in_seconds: float
    out_seconds: float
    decision: str = "maybe"
    comment: str = ""
    story_role: str | None = None
    audio_intent: str = "undecided"
    origin: str = "user"


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS preeditor_schema (
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS preeditor_projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    target_duration REAL CHECK(target_duration IS NULL OR target_duration > 0),
    orientation TEXT NOT NULL CHECK(orientation IN ('landscape','portrait','undecided')),
    intent TEXT NOT NULL DEFAULT '',
    ideal_clip_duration REAL NOT NULL DEFAULT 8 CHECK(ideal_clip_duration > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preeditor_source_roots (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES preeditor_projects(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    recursive INTEGER NOT NULL DEFAULT 1 CHECK(recursive IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id,path)
);
CREATE TABLE IF NOT EXISTS preeditor_sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES preeditor_projects(id) ON DELETE CASCADE,
    root_id TEXT NOT NULL REFERENCES preeditor_source_roots(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    current_path TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    filename TEXT NOT NULL,
    captured_at TEXT,
    duration REAL,
    width INTEGER,
    height INTEGER,
    fps REAL,
    codec TEXT,
    size_bytes INTEGER,
    has_audio INTEGER,
    rotation INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('ready','offline','error','unsupported')),
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(root_id,relative_path)
);
CREATE INDEX IF NOT EXISTS preeditor_sources_project_idx
    ON preeditor_sources(project_id,captured_at,relative_path);
CREATE TABLE IF NOT EXISTS preeditor_suggestions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES preeditor_projects(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES preeditor_sources(id) ON DELETE CASCADE,
    in_seconds REAL NOT NULL CHECK(in_seconds >= 0),
    out_seconds REAL NOT NULL CHECK(out_seconds > in_seconds),
    score REAL NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL DEFAULT '',
    analysis_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(source_id,in_seconds,out_seconds,analysis_version)
);
CREATE TABLE IF NOT EXISTS preeditor_selections (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES preeditor_projects(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES preeditor_sources(id) ON DELETE RESTRICT,
    in_seconds REAL NOT NULL CHECK(in_seconds >= 0),
    out_seconds REAL NOT NULL CHECK(out_seconds > in_seconds),
    decision TEXT NOT NULL CHECK(decision IN ('keep','maybe','skip')),
    comment TEXT NOT NULL DEFAULT '',
    story_role TEXT CHECK(story_role IS NULL OR story_role IN ('opening','transition','peak','ending')),
    audio_intent TEXT NOT NULL DEFAULT 'undecided'
        CHECK(audio_intent IN ('undecided','mute','preserve','speech','background')),
    treatment_json TEXT NOT NULL DEFAULT '{}',
    origin TEXT NOT NULL DEFAULT 'user',
    archived_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS preeditor_selections_project_idx
    ON preeditor_selections(project_id,decision,created_at);
CREATE TABLE IF NOT EXISTS preeditor_selection_markers (
    id TEXT PRIMARY KEY,
    selection_id TEXT NOT NULL REFERENCES preeditor_selections(id) ON DELETE CASCADE,
    source_seconds REAL NOT NULL CHECK(source_seconds >= 0),
    comment TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preeditor_sequences (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES preeditor_projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target_duration REAL CHECK(target_duration IS NULL OR target_duration > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preeditor_sequence_versions (
    id TEXT PRIMARY KEY,
    sequence_id TEXT NOT NULL REFERENCES preeditor_sequences(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK(version > 0),
    parent_version_id TEXT REFERENCES preeditor_sequence_versions(id) ON DELETE SET NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(sequence_id,version)
);
CREATE TABLE IF NOT EXISTS preeditor_sequence_items (
    version_id TEXT NOT NULL REFERENCES preeditor_sequence_versions(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK(position > 0),
    selection_id TEXT NOT NULL REFERENCES preeditor_selections(id) ON DELETE RESTRICT,
    PRIMARY KEY(version_id,position),
    UNIQUE(version_id,selection_id)
);
CREATE TABLE IF NOT EXISTS preeditor_proposals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES preeditor_projects(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected')),
    explanation TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT
);
"""


class PreEditor:
    """Deep module for reusable projects, selections, sequences, and proposals.

    The database is its persistence implementation. Callers use this interface
    rather than depending on table layout or row identifiers.
    """

    def __init__(self, database: Path):
        self.database = database.expanduser().resolve()
        self._proposal_lock = threading.Lock()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)
            project_columns = {
                str(row["name"]) for row in connection.execute("PRAGMA table_info(preeditor_projects)")
            }
            if "ideal_clip_duration" not in project_columns:
                connection.execute(
                    "ALTER TABLE preeditor_projects ADD COLUMN ideal_clip_duration REAL NOT NULL DEFAULT 8"
                )
            row = connection.execute("SELECT version FROM preeditor_schema LIMIT 1").fetchone()
            if row is None:
                connection.execute("INSERT INTO preeditor_schema(version) VALUES(?)", (SCHEMA_VERSION,))
            elif int(row["version"]) == 1:
                self._backup_before_migration(connection, 1)
                selection_columns = {
                    str(item["name"]) for item in connection.execute("PRAGMA table_info(preeditor_selections)")
                }
                if "archived_at" not in selection_columns:
                    connection.execute("ALTER TABLE preeditor_selections ADD COLUMN archived_at TEXT")
                connection.execute("UPDATE preeditor_schema SET version=?", (SCHEMA_VERSION,))
            elif int(row["version"]) != SCHEMA_VERSION:
                raise RuntimeError(
                    f"Unsupported pre-editor schema {row['version']}; expected {SCHEMA_VERSION}."
                )

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _backup_before_migration(self, connection: sqlite3.Connection, version: int) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = self.database.with_name(f"{self.database.stem}.schema-{version}.{stamp}.backup.sqlite3")
        backup = sqlite3.connect(destination)
        try:
            connection.backup(backup)
        finally:
            backup.close()
        return destination

    def backup_database(self, destination: Path | None = None) -> Path:
        """Create a consistent SQLite backup while the app remains open."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = (destination or self.database.with_name(f"{self.database.stem}.{stamp}.backup.sqlite3")).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = sqlite3.connect(target)
        try:
            with self.connection() as source:
                source.backup(backup)
        finally:
            backup.close()
        return target

    def create_project(self, options: ProjectOptions) -> dict[str, Any]:
        name = options.name.strip()
        if not name:
            raise ValueError("Project name is required.")
        if options.orientation not in ORIENTATIONS:
            raise ValueError("Orientation must be landscape, portrait, or undecided.")
        if options.target_duration is not None and options.target_duration <= 0:
            raise ValueError("Target duration must be positive.")
        if options.ideal_clip_duration <= 0:
            raise ValueError("Ideal clip duration must be positive.")
        now = utc_now()
        project_id = new_id("project")
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO preeditor_projects(
                       id,name,target_duration,orientation,intent,ideal_clip_duration,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    project_id,
                    name[:120],
                    options.target_duration,
                    options.orientation,
                    options.intent.strip()[:8_000],
                    options.ideal_clip_duration,
                    now,
                    now,
                ),
            )
        return self.project(project_id) or {}

    def project(self, project_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM preeditor_projects WHERE id=?", (project_id,)
            ).fetchone()
        return dict(row) if row else None

    def projects(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM preeditor_projects ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def update_project(self, project_id: str, **changes: Any) -> dict[str, Any]:
        existing = self.project(project_id)
        if not existing:
            raise KeyError(project_id)
        allowed = {"name", "target_duration", "orientation", "intent", "ideal_clip_duration"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported project changes: {sorted(unknown)}")
        options = ProjectOptions(
            name=str(changes.get("name", existing["name"])),
            target_duration=(
                None if changes.get("target_duration", existing["target_duration"]) in {None, ""}
                else float(changes.get("target_duration", existing["target_duration"]))
            ),
            orientation=str(changes.get("orientation", existing["orientation"])),
            intent=str(changes.get("intent", existing["intent"])),
            ideal_clip_duration=float(changes.get("ideal_clip_duration", existing["ideal_clip_duration"])),
        )
        if not options.name.strip():
            raise ValueError("Project name is required.")
        if options.orientation not in ORIENTATIONS:
            raise ValueError("Orientation must be landscape, portrait, or undecided.")
        if options.target_duration is not None and options.target_duration <= 0:
            raise ValueError("Target duration must be positive.")
        if options.ideal_clip_duration <= 0:
            raise ValueError("Ideal clip duration must be positive.")
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """UPDATE preeditor_projects SET name=?,target_duration=?,orientation=?,intent=?,
                          ideal_clip_duration=?,updated_at=? WHERE id=?""",
                (options.name.strip()[:120], options.target_duration, options.orientation,
                 options.intent.strip()[:8_000], options.ideal_clip_duration, now, project_id),
            )
        return self.project(project_id) or {}

    def add_source_root(
        self,
        project_id: str,
        path: Path,
        *,
        label: str = "",
        recursive: bool = True,
    ) -> dict[str, Any]:
        if not self.project(project_id):
            raise KeyError(project_id)
        resolved = path.expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise NotADirectoryError(str(resolved))
        now = utc_now()
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM preeditor_source_roots WHERE project_id=? AND path=?",
                (project_id, str(resolved)),
            ).fetchone()
            if existing:
                connection.execute(
                    """UPDATE preeditor_source_roots
                       SET label=?,recursive=?,updated_at=? WHERE id=?""",
                    (label.strip()[:80], int(recursive), now, existing["id"]),
                )
                root_id = str(existing["id"])
            else:
                root_id = new_id("root")
                connection.execute(
                    """INSERT INTO preeditor_source_roots(
                           id,project_id,path,label,recursive,created_at,updated_at
                       ) VALUES(?,?,?,?,?,?,?)""",
                    (root_id, project_id, str(resolved), label.strip()[:80], int(recursive), now, now),
                )
        return self.source_root(root_id) or {}

    def source_root(self, root_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM preeditor_source_roots WHERE id=?", (root_id,)
            ).fetchone()
        return dict(row) if row else None

    def source_roots(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM preeditor_source_roots WHERE project_id=? ORDER BY created_at",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _paths_for_root(root: Mapping[str, Any]) -> list[Path]:
        base = Path(str(root["path"]))
        iterator = base.rglob("*") if bool(root["recursive"]) else base.iterdir()
        return sorted(
            (path for path in iterator if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS),
            key=lambda path: str(path.relative_to(base)).lower(),
        )

    @staticmethod
    def _fingerprint(metadata: VideoMetadata) -> str:
        digest = hashlib.sha256()
        digest.update(f"{metadata.size_bytes}|{metadata.duration:.3f}".encode("utf-8"))
        path = Path(metadata.path)
        with path.open("rb") as stream:
            digest.update(stream.read(65_536))
            if metadata.size_bytes > 65_536:
                stream.seek(max(0, metadata.size_bytes - 65_536))
                digest.update(stream.read(65_536))
        return digest.hexdigest()

    def scan(
        self,
        project_id: str,
        *,
        probe: Callable[[Path], VideoMetadata] = probe_video,
    ) -> dict[str, Any]:
        roots = self.source_roots(project_id)
        if not roots:
            raise ValueError("Add at least one footage folder before scanning.")
        now = utc_now()
        discovered: set[tuple[str, str]] = set()
        ready = 0
        failures: list[dict[str, str]] = []
        with self.connection() as connection:
            for root in roots:
                root_path = Path(str(root["path"]))
                if not root_path.is_dir():
                    connection.execute(
                        "UPDATE preeditor_sources SET status='offline',updated_at=? WHERE root_id=?",
                        (now, root["id"]),
                    )
                    failures.append({"path": str(root_path), "error": "Footage folder is offline."})
                    continue
                for path in self._paths_for_root(root):
                    relative = str(path.relative_to(root_path))
                    discovered.add((str(root["id"]), relative))
                    existing = connection.execute(
                        "SELECT * FROM preeditor_sources WHERE root_id=? AND relative_path=?",
                        (root["id"], relative),
                    ).fetchone()
                    try:
                        metadata = probe(path)
                        fingerprint = self._fingerprint(metadata)
                        moved = None
                        if existing is None:
                            candidates = connection.execute(
                                """SELECT * FROM preeditor_sources
                                   WHERE project_id=? AND fingerprint=?""",
                                (project_id, fingerprint),
                            ).fetchall()
                            moved = next(
                                (row for row in candidates if not Path(str(row["current_path"])).exists()),
                                None,
                            )
                        if moved is not None:
                            connection.execute(
                                """UPDATE preeditor_sources SET root_id=?,relative_path=?,current_path=?,
                                       filename=?,captured_at=?,duration=?,width=?,height=?,fps=?,codec=?,size_bytes=?,
                                       has_audio=?,rotation=?,status='ready',error='',updated_at=? WHERE id=?""",
                                (
                                    root["id"], relative, metadata.path, metadata.filename, metadata.captured_at,
                                    metadata.duration, metadata.width, metadata.height, metadata.fps, metadata.codec,
                                    metadata.size_bytes, int(metadata.has_audio), metadata.rotation, now, moved["id"],
                                ),
                            )
                            ready += 1
                            continue
                        source_id = str(existing["id"]) if existing else new_id("source")
                        created_at = str(existing["created_at"]) if existing else now
                        connection.execute(
                            """INSERT INTO preeditor_sources(
                                   id,project_id,root_id,relative_path,current_path,fingerprint,
                                   filename,captured_at,duration,width,height,fps,codec,size_bytes,
                                   has_audio,rotation,status,error,created_at,updated_at
                               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ready','',?,?)
                               ON CONFLICT(root_id,relative_path) DO UPDATE SET
                                 current_path=excluded.current_path,
                                 fingerprint=excluded.fingerprint,
                                 filename=excluded.filename,
                                 captured_at=excluded.captured_at,
                                 duration=excluded.duration,
                                 width=excluded.width,
                                 height=excluded.height,
                                 fps=excluded.fps,
                                 codec=excluded.codec,
                                 size_bytes=excluded.size_bytes,
                                 has_audio=excluded.has_audio,
                                 rotation=excluded.rotation,
                                 status='ready',error='',updated_at=excluded.updated_at""",
                            (
                                source_id,
                                project_id,
                                root["id"],
                                relative,
                                metadata.path,
                                fingerprint,
                                metadata.filename,
                                metadata.captured_at,
                                metadata.duration,
                                metadata.width,
                                metadata.height,
                                metadata.fps,
                                metadata.codec,
                                metadata.size_bytes,
                                int(metadata.has_audio),
                                metadata.rotation,
                                created_at,
                                now,
                            ),
                        )
                        ready += 1
                    except Exception as exc:
                        source_id = str(existing["id"]) if existing else new_id("source")
                        created_at = str(existing["created_at"]) if existing else now
                        stat_size = path.stat().st_size if path.exists() else 0
                        connection.execute(
                            """INSERT INTO preeditor_sources(
                                   id,project_id,root_id,relative_path,current_path,fingerprint,
                                   filename,size_bytes,status,error,created_at,updated_at
                               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                               ON CONFLICT(root_id,relative_path) DO UPDATE SET
                                 current_path=excluded.current_path,filename=excluded.filename,
                                 size_bytes=excluded.size_bytes,status='error',error=excluded.error,
                                 updated_at=excluded.updated_at""",
                            (
                                source_id,
                                project_id,
                                root["id"],
                                relative,
                                str(path.resolve()),
                                hashlib.sha256(f"{relative}|{stat_size}".encode()).hexdigest(),
                                path.name,
                                stat_size,
                                "error",
                                str(exc)[:1_000],
                                created_at,
                                now,
                            ),
                        )
                        failures.append({"path": str(path), "error": str(exc)})

            rows = connection.execute(
                "SELECT id,root_id,relative_path FROM preeditor_sources WHERE project_id=?",
                (project_id,),
            ).fetchall()
            for row in rows:
                if (str(row["root_id"]), str(row["relative_path"])) not in discovered:
                    connection.execute(
                        "UPDATE preeditor_sources SET status='offline',updated_at=? WHERE id=?",
                        (now, row["id"]),
                    )
            connection.execute(
                "UPDATE preeditor_projects SET updated_at=? WHERE id=?", (now, project_id)
            )
        return {
            "project_id": project_id,
            "ready": ready,
            "failures": failures,
            "sources": self.sources(project_id),
        }

    def sources(self, project_id: str, *, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM preeditor_sources WHERE project_id=?"
        parameters: list[Any] = [project_id]
        if status:
            query += " AND status=?"
            parameters.append(status)
        query += " ORDER BY captured_at,relative_path"
        with self.connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def source(self, source_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM preeditor_sources WHERE id=?", (source_id,)
            ).fetchone()
        return dict(row) if row else None

    def relink_source(self, source_id: str, path: Path, *, probe: Callable[[Path], VideoMetadata] = probe_video) -> dict[str, Any]:
        source = self.source(source_id)
        if not source:
            raise KeyError(source_id)
        metadata = probe(path.expanduser().resolve(strict=True))
        if int(source.get("size_bytes") or 0) and metadata.size_bytes != int(source["size_bytes"]):
            raise ValueError("The replacement file does not match the original file size.")
        fingerprint = self._fingerprint(metadata)
        if source.get("fingerprint") and fingerprint != source["fingerprint"]:
            raise ValueError("The replacement file does not match the original source.")
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """UPDATE preeditor_sources SET current_path=?,fingerprint=?,filename=?,captured_at=?,
                       duration=?,width=?,height=?,fps=?,codec=?,size_bytes=?,has_audio=?,rotation=?,status='ready',error='',updated_at=?
                   WHERE id=?""",
                (
                    metadata.path,
                    fingerprint,
                    metadata.filename,
                    metadata.captured_at,
                    metadata.duration,
                    metadata.width,
                    metadata.height,
                    metadata.fps,
                    metadata.codec,
                    metadata.size_bytes,
                    int(metadata.has_audio),
                    metadata.rotation,
                    now,
                    source_id,
                ),
            )
        return self.source(source_id) or {}

    def create_selection(self, project_id: str, draft: SelectionDraft) -> dict[str, Any]:
        source = self.source(draft.source_id)
        if not source or source["project_id"] != project_id:
            raise KeyError(draft.source_id)
        self._validate_selection(source, draft)
        now = utc_now()
        selection_id = new_id("selection")
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO preeditor_selections(
                       id,project_id,source_id,in_seconds,out_seconds,decision,comment,
                       story_role,audio_intent,origin,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    selection_id,
                    project_id,
                    draft.source_id,
                    draft.in_seconds,
                    draft.out_seconds,
                    draft.decision,
                    draft.comment.strip()[:8_000],
                    draft.story_role,
                    draft.audio_intent,
                    draft.origin[:80],
                    now,
                    now,
                ),
            )
        return self.selection(selection_id) or {}

    @staticmethod
    def _validate_selection(source: Mapping[str, Any], draft: SelectionDraft) -> None:
        if draft.decision not in DECISIONS:
            raise ValueError("Decision must be keep, maybe, or skip.")
        if draft.story_role not in STORY_ROLES | {None}:
            raise ValueError("Invalid story role.")
        if draft.audio_intent not in AUDIO_INTENTS:
            raise ValueError("Invalid audio intent.")
        if draft.in_seconds < 0 or draft.out_seconds <= draft.in_seconds:
            raise ValueError("A selection requires non-negative In and later Out points.")
        duration = source.get("duration")
        if duration is None or draft.out_seconds > float(duration) + 0.001:
            raise ValueError("Selection extends beyond the source duration.")

    def selection(self, selection_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT s.*,m.filename,m.current_path,m.duration source_duration,m.width,m.height,
                          m.fps,m.codec,m.has_audio,m.rotation,m.status source_status,r.label source_label
                   FROM preeditor_selections s
                   JOIN preeditor_sources m ON m.id=s.source_id
                   JOIN preeditor_source_roots r ON r.id=m.root_id
                   WHERE s.id=?""",
                (selection_id,),
            ).fetchone()
        return self._selection_payload(row) if row else None

    @staticmethod
    def _selection_payload(row: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload["duration"] = float(payload["out_seconds"]) - float(payload["in_seconds"])
        payload["treatment"] = json.loads(str(payload.pop("treatment_json")))
        return payload

    def selections(self, project_id: str, *, decision: str | None = None) -> list[dict[str, Any]]:
        query = """SELECT s.*,m.filename,m.current_path,m.duration source_duration,m.width,m.height,
                          m.fps,m.codec,m.has_audio,m.rotation,m.status source_status,r.label source_label
                   FROM preeditor_selections s
                   JOIN preeditor_sources m ON m.id=s.source_id
                   JOIN preeditor_source_roots r ON r.id=m.root_id
                   WHERE s.project_id=? AND s.archived_at IS NULL"""
        parameters: list[Any] = [project_id]
        if decision:
            if decision not in DECISIONS:
                raise ValueError("Decision must be keep, maybe, or skip.")
            query += " AND s.decision=?"
            parameters.append(decision)
        query += " ORDER BY m.captured_at,s.created_at"
        with self.connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._selection_payload(row) for row in rows]

    def archive_selection(self, selection_id: str) -> dict[str, Any]:
        existing = self.selection(selection_id)
        if not existing:
            raise KeyError(selection_id)
        archived_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                "UPDATE preeditor_selections SET archived_at=?,updated_at=? WHERE id=?",
                (archived_at, archived_at, selection_id),
            )
        return self.selection(selection_id) or {}

    def update_selection(self, selection_id: str, **changes: Any) -> dict[str, Any]:
        existing = self.selection(selection_id)
        if not existing:
            raise KeyError(selection_id)
        allowed = {"in_seconds", "out_seconds", "decision", "comment", "story_role", "audio_intent", "treatment"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unsupported selection changes: {sorted(unknown)}")
        draft = SelectionDraft(
            source_id=str(existing["source_id"]),
            in_seconds=float(changes.get("in_seconds", existing["in_seconds"])),
            out_seconds=float(changes.get("out_seconds", existing["out_seconds"])),
            decision=str(changes.get("decision", existing["decision"])),
            comment=str(changes.get("comment", existing["comment"])),
            story_role=changes.get("story_role", existing["story_role"]),
            audio_intent=str(changes.get("audio_intent", existing["audio_intent"])),
            origin=str(existing["origin"]),
        )
        source = self.source(draft.source_id)
        if not source:
            raise KeyError(draft.source_id)
        self._validate_selection(source, draft)
        treatment = changes.get("treatment", existing["treatment"])
        if not isinstance(treatment, Mapping):
            raise ValueError("Treatment must be an object.")
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """UPDATE preeditor_selections SET in_seconds=?,out_seconds=?,decision=?,comment=?,
                       story_role=?,audio_intent=?,treatment_json=?,updated_at=? WHERE id=?""",
                (
                    draft.in_seconds,
                    draft.out_seconds,
                    draft.decision,
                    draft.comment.strip()[:8_000],
                    draft.story_role,
                    draft.audio_intent,
                    json.dumps(dict(treatment), sort_keys=True),
                    now,
                    selection_id,
                ),
            )
        return self.selection(selection_id) or {}

    def add_marker(self, selection_id: str, source_seconds: float, comment: str) -> dict[str, Any]:
        selection = self.selection(selection_id)
        if not selection:
            raise KeyError(selection_id)
        if not float(selection["in_seconds"]) <= source_seconds <= float(selection["out_seconds"]):
            raise ValueError("Marker must be inside the selected range.")
        clean = comment.strip()
        if not clean:
            raise ValueError("Marker comment is required.")
        marker_id = new_id("marker")
        created_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO preeditor_selection_markers(
                       id,selection_id,source_seconds,comment,created_at
                   ) VALUES(?,?,?,?,?)""",
                (marker_id, selection_id, source_seconds, clean[:4_000], created_at),
            )
        return {
            "id": marker_id,
            "selection_id": selection_id,
            "source_seconds": source_seconds,
            "comment": clean[:4_000],
            "created_at": created_at,
        }

    def markers(self, selection_id: str) -> list[dict[str, Any]]:
        if not self.selection(selection_id):
            raise KeyError(selection_id)
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM preeditor_selection_markers
                   WHERE selection_id=? ORDER BY source_seconds,created_at""",
                (selection_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_sequence(
        self,
        project_id: str,
        name: str,
        selection_ids: Sequence[str],
        *,
        target_duration: float | None = None,
        note: str = "Initial sequence",
    ) -> dict[str, Any]:
        if not self.project(project_id):
            raise KeyError(project_id)
        if target_duration is not None and target_duration <= 0:
            raise ValueError("Target duration must be positive.")
        sequence_id = new_id("sequence")
        now = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO preeditor_sequences(
                       id,project_id,name,target_duration,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?)""",
                (sequence_id, project_id, name.strip()[:120] or "First cut", target_duration, now, now),
            )
        return self.revise_sequence(sequence_id, selection_ids, note=note)

    def revise_sequence(
        self,
        sequence_id: str,
        selection_ids: Sequence[str],
        *,
        note: str = "",
    ) -> dict[str, Any]:
        if len(set(selection_ids)) != len(selection_ids):
            raise ValueError("A sequence version cannot contain the same selection twice.")
        with self.connection() as connection:
            sequence = connection.execute(
                "SELECT * FROM preeditor_sequences WHERE id=?", (sequence_id,)
            ).fetchone()
            if not sequence:
                raise KeyError(sequence_id)
            if selection_ids:
                placeholders = ",".join("?" for _ in selection_ids)
                rows = connection.execute(
                    f"""SELECT id FROM preeditor_selections
                         WHERE project_id=? AND id IN ({placeholders})""",
                    (sequence["project_id"], *selection_ids),
                ).fetchall()
                if len(rows) != len(selection_ids):
                    raise ValueError("Every sequence item must be a selection from this project.")
            previous = connection.execute(
                """SELECT * FROM preeditor_sequence_versions
                   WHERE sequence_id=? ORDER BY version DESC LIMIT 1""",
                (sequence_id,),
            ).fetchone()
            version_number = int(previous["version"]) + 1 if previous else 1
            version_id = new_id("version")
            now = utc_now()
            connection.execute(
                """INSERT INTO preeditor_sequence_versions(
                       id,sequence_id,version,parent_version_id,note,created_at
                   ) VALUES(?,?,?,?,?,?)""",
                (
                    version_id,
                    sequence_id,
                    version_number,
                    previous["id"] if previous else None,
                    note.strip()[:2_000],
                    now,
                ),
            )
            connection.executemany(
                """INSERT INTO preeditor_sequence_items(version_id,position,selection_id)
                   VALUES(?,?,?)""",
                [(version_id, position, selection_id) for position, selection_id in enumerate(selection_ids, 1)],
            )
            connection.execute(
                "UPDATE preeditor_sequences SET updated_at=? WHERE id=?", (now, sequence_id)
            )
        return self.sequence_version(version_id)

    def sequence_version(self, version_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            version = connection.execute(
                """SELECT v.*,s.project_id,s.name sequence_name,s.target_duration
                   FROM preeditor_sequence_versions v
                   JOIN preeditor_sequences s ON s.id=v.sequence_id WHERE v.id=?""",
                (version_id,),
            ).fetchone()
            if not version:
                raise KeyError(version_id)
            rows = connection.execute(
                """SELECT i.position,x.*,m.filename,m.current_path,m.duration source_duration,
                          m.width,m.height,m.fps,m.codec,m.has_audio,m.rotation,m.status source_status,r.label source_label
                   FROM preeditor_sequence_items i
                   JOIN preeditor_selections x ON x.id=i.selection_id
                   JOIN preeditor_sources m ON m.id=x.source_id
                   JOIN preeditor_source_roots r ON r.id=m.root_id
                   WHERE i.version_id=? ORDER BY i.position""",
                (version_id,),
            ).fetchall()
        items = [self._selection_payload(row) for row in rows]
        return {
            **dict(version),
            "items": items,
            "duration": sum(float(item["duration"]) for item in items),
        }

    def latest_sequence_version(self, sequence_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT id FROM preeditor_sequence_versions
                   WHERE sequence_id=? ORDER BY version DESC LIMIT 1""",
                (sequence_id,),
            ).fetchone()
        if not row:
            raise KeyError(sequence_id)
        return self.sequence_version(str(row["id"]))

    def sequences(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT s.*,MAX(v.version) latest_version
                   FROM preeditor_sequences s
                   LEFT JOIN preeditor_sequence_versions v ON v.sequence_id=s.id
                   WHERE s.project_id=? GROUP BY s.id ORDER BY s.updated_at DESC""",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_proposal(
        self,
        project_id: str,
        *,
        provider: str,
        model: str,
        kind: str,
        payload: Mapping[str, Any],
        explanation: str = "",
    ) -> dict[str, Any]:
        if not self.project(project_id):
            raise KeyError(project_id)
        proposal_id = new_id("proposal")
        created_at = utc_now()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO preeditor_proposals(
                       id,project_id,provider,model,kind,status,explanation,payload_json,created_at
                   ) VALUES(?,?,?,?,?,'pending',?,?,?)""",
                (
                    proposal_id,
                    project_id,
                    provider.strip()[:80],
                    model.strip()[:120],
                    kind.strip()[:80],
                    explanation.strip()[:8_000],
                    json.dumps(dict(payload), sort_keys=True),
                    created_at,
                ),
            )
        return self.proposal(proposal_id) or {}

    def proposal(self, proposal_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM preeditor_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["payload"] = json.loads(str(payload.pop("payload_json")))
        return payload

    def decide_proposal(self, proposal_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"accepted", "rejected"}:
            raise ValueError("Proposal decision must be accepted or rejected.")
        with self.connection() as connection:
            result = connection.execute(
                """UPDATE preeditor_proposals SET status=?,decided_at=?
                   WHERE id=? AND status='pending'""",
                (decision, utc_now(), proposal_id),
            )
            if result.rowcount != 1:
                raise KeyError(proposal_id)
        return self.proposal(proposal_id) or {}

    def apply_proposal(self, proposal_id: str) -> dict[str, Any]:
        # Application is deliberately serialized: a double-click or two local
        # clients cannot create two sequence versions from one pending proposal.
        with self._proposal_lock:
            return self._apply_proposal_unlocked(proposal_id)

    def _apply_proposal_unlocked(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.proposal(proposal_id)
        if not proposal or proposal["status"] != "pending":
            raise KeyError(proposal_id)
        payload = proposal["payload"]
        result: dict[str, Any]
        if proposal["kind"] == "sequence":
            selection_ids = payload.get("selection_ids")
            if not isinstance(selection_ids, list) or not all(isinstance(item, str) for item in selection_ids):
                raise ValueError("A sequence proposal requires a selection_ids string array.")
            sequence_id = payload.get("sequence_id")
            if sequence_id:
                result = self.revise_sequence(
                    str(sequence_id), selection_ids, note=str(payload.get("note") or proposal["explanation"])
                )
            else:
                result = self.create_sequence(
                    proposal["project_id"], str(payload.get("name") or "Assistant proposal"), selection_ids,
                    target_duration=payload.get("target_duration"),
                    note=str(payload.get("note") or proposal["explanation"]),
                )
        elif proposal["kind"] == "selection_updates":
            updates = payload.get("updates")
            if not isinstance(updates, list):
                raise ValueError("A selection update proposal requires an updates array.")
            applied = []
            for update in updates:
                if not isinstance(update, Mapping) or not isinstance(update.get("selection_id"), str):
                    raise ValueError("Every proposed update needs a selection_id.")
                selection_id = str(update["selection_id"])
                selection = self.selection(selection_id)
                if not selection or selection["project_id"] != proposal["project_id"]:
                    raise ValueError("A proposed selection does not belong to this project.")
                changes = {key: value for key, value in update.items() if key != "selection_id"}
                applied.append(self.update_selection(selection_id, **changes))
            result = {"updated": applied}
        else:
            raise ValueError(f"Unsupported proposal kind: {proposal['kind']}")
        accepted = self.decide_proposal(proposal_id, "accepted")
        return {"proposal": accepted, "result": result}

    def proposals(self, project_id: str, *, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM preeditor_proposals WHERE project_id=?"
        parameters: list[Any] = [project_id]
        if status:
            if status not in {"pending", "accepted", "rejected"}:
                raise ValueError("Invalid proposal status.")
            query += " AND status=?"
            parameters.append(status)
        query += " ORDER BY created_at DESC"
        with self.connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        result = []
        for row in rows:
            payload = dict(row)
            payload["payload"] = json.loads(str(payload.pop("payload_json")))
            result.append(payload)
        return result

    def project_manifest(self, project_id: str) -> dict[str, Any]:
        project = self.project(project_id)
        if not project:
            raise KeyError(project_id)
        roots = self.source_roots(project_id)
        for root in roots:
            root.pop("path", None)
        sources = self.sources(project_id)
        for source in sources:
            source.pop("current_path", None)
            source.pop("fingerprint", None)
        selections = self.selections(project_id)
        for selection in selections:
            selection.pop("current_path", None)
        sequences = [
            self.latest_sequence_version(sequence["id"])
            for sequence in self.sequences(project_id)
        ]
        for sequence in sequences:
            for item in sequence["items"]:
                item.pop("current_path", None)
        return {
            "format": "selects-project",
            "version": SCHEMA_VERSION,
            "exported_at": utc_now(),
            "project": project,
            "source_roots": roots,
            "sources": sources,
            "selections": selections,
            "sequences": sequences,
            "proposals": self.proposals(project_id),
        }

    def project_context(self, project_id: str) -> dict[str, Any]:
        """Return the bounded, media-free context suitable for an assistant."""
        project = self.project(project_id)
        if not project:
            raise KeyError(project_id)
        all_selections = self.selections(project_id)
        selections = all_selections[:2_000]
        selected_source_ids = {str(item["source_id"]) for item in selections}
        all_sources = self.sources(project_id)
        prioritized = sorted(all_sources, key=lambda item: str(item["id"]) not in selected_source_ids)
        sources = [
            {key: item.get(key) for key in (
                "id", "filename", "captured_at", "duration", "width", "height", "fps",
                "has_audio", "rotation", "status", "error",
            )}
            for item in prioritized[:500]
        ]
        portable_selections = []
        for item in selections:
            clean = dict(item)
            clean.pop("current_path", None)
            portable_selections.append(clean)
        return {
            "format": "selects-agent-context",
            "version": 1,
            "project": project,
            "sources": sources,
            "selections": portable_selections,
            "sequences": self.sequences(project_id),
            "counts": {
                "sources": len(all_sources), "sources_included": len(sources),
                "selections": len(all_selections), "selections_included": len(portable_selections),
            },
        }
