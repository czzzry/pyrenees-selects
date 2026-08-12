from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.media import require_media_tools
from pyrenees_selects.preeditor import PreEditor


LEGACY_SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE preeditor_schema(version INTEGER NOT NULL);
CREATE TABLE preeditor_projects(
 id TEXT PRIMARY KEY,name TEXT NOT NULL,target_duration REAL,orientation TEXT NOT NULL,
 intent TEXT NOT NULL DEFAULT '',ideal_clip_duration REAL NOT NULL DEFAULT 8,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE preeditor_source_roots(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES preeditor_projects(id),path TEXT NOT NULL,
 label TEXT NOT NULL DEFAULT '',recursive INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,UNIQUE(project_id,path));
CREATE TABLE preeditor_sources(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES preeditor_projects(id),
 root_id TEXT NOT NULL REFERENCES preeditor_source_roots(id),relative_path TEXT NOT NULL,
 current_path TEXT NOT NULL,fingerprint TEXT NOT NULL,filename TEXT NOT NULL,captured_at TEXT,
 duration REAL,width INTEGER,height INTEGER,fps REAL,codec TEXT,size_bytes INTEGER,has_audio INTEGER,
 rotation INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,error TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(root_id,relative_path));
CREATE TABLE preeditor_selections(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES preeditor_projects(id),
 source_id TEXT NOT NULL REFERENCES preeditor_sources(id),in_seconds REAL NOT NULL,out_seconds REAL NOT NULL,
 decision TEXT NOT NULL,comment TEXT NOT NULL DEFAULT '',story_role TEXT,audio_intent TEXT NOT NULL DEFAULT 'undecided',
 treatment_json TEXT NOT NULL DEFAULT '{}',origin TEXT NOT NULL DEFAULT 'user',archived_at TEXT,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE preeditor_selection_markers(
 id TEXT PRIMARY KEY,selection_id TEXT NOT NULL REFERENCES preeditor_selections(id),
 source_seconds REAL NOT NULL,comment TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE preeditor_sequences(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES preeditor_projects(id),name TEXT NOT NULL,
 target_duration REAL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE preeditor_sequence_versions(
 id TEXT PRIMARY KEY,sequence_id TEXT NOT NULL REFERENCES preeditor_sequences(id),version INTEGER NOT NULL,
 parent_version_id TEXT,note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,UNIQUE(sequence_id,version));
CREATE TABLE preeditor_sequence_items(
 version_id TEXT NOT NULL REFERENCES preeditor_sequence_versions(id),position INTEGER NOT NULL,
 selection_id TEXT NOT NULL REFERENCES preeditor_selections(id),PRIMARY KEY(version_id,position),
 UNIQUE(version_id,selection_id));
"""


class LegacyMigrationTests(unittest.TestCase):
    def test_real_v2_layout_is_reprobed_mapped_and_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "legacy.mp4"
            ffmpeg, _ = require_media_tools()
            subprocess.run(
                [ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                 "testsrc2=size=160x90:rate=10:duration=2", "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", "-y", str(source)],
                check=True, capture_output=True,
            )
            database = root / "legacy.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript(LEGACY_SCHEMA)
            now = "2026-01-01T00:00:00+00:00"
            connection.execute("INSERT INTO preeditor_schema VALUES(2)")
            connection.execute(
                "INSERT INTO preeditor_projects VALUES(?,?,?,?,?,?,?,?)",
                ("p", "Legacy", 60, "portrait", "", 4, now, now),
            )
            connection.execute(
                "INSERT INTO preeditor_source_roots VALUES(?,?,?,?,?,?,?)",
                ("r", "p", str(root), "Legacy", 0, now, now),
            )
            connection.execute(
                "INSERT INTO preeditor_sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("s", "p", "r", source.name, str(source), "legacy-fingerprint", source.name,
                 now, 2, 160, 90, 10, "h264", source.stat().st_size, 0, 0, "ready", "", now, now),
            )
            connection.execute(
                "INSERT INTO preeditor_selections VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("x", "p", "s", 0.4, 1.4, "keep", "Frozen legacy note", "opening",
                 "preserve", "{}", "user", None, now, now),
            )
            connection.execute(
                "INSERT INTO preeditor_sequences VALUES(?,?,?,?,?,?)",
                ("q", "p", "Legacy cut", 60, now, now),
            )
            connection.execute(
                "INSERT INTO preeditor_sequence_versions VALUES(?,?,?,?,?,?)",
                ("v", "q", 1, None, "Before migration", now),
            )
            connection.execute("INSERT INTO preeditor_sequence_items VALUES(?,?,?)", ("v", 1, "x"))
            connection.commit()
            connection.close()

            editor = PreEditor(database)
            project = editor.project("p")
            self.assertEqual(
                (project["shot_rhythm"], project["shot_min_seconds"], project["shot_max_seconds"]),
                ("energetic", 3, 5),
            )
            self.assertEqual(project["target_duration_seconds"], 60)
            source_row = editor.assert_source_unchanged("s")
            self.assertEqual(source_row["fingerprint"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertFalse(source_row["is_vfr"])
            frozen = editor.sequence_version("v")
            self.assertEqual(frozen["orientation"], "portrait")
            self.assertEqual((frozen["items"][0]["in_us"], frozen["items"][0]["out_us"]), (400_000, 1_400_000))
            editor.update_selection("x", in_seconds=0.8, out_seconds=1.8, comment="Changed later")
            self.assertEqual(editor.sequence_version("v")["items"][0]["comment"], "Frozen legacy note")
            self.assertTrue(list(root.glob("legacy.schema-2.*.backup.sqlite3")))


if __name__ == "__main__":
    unittest.main()
