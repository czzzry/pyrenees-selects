import tempfile
import threading
import unittest
from pathlib import Path

from pyrenees_selects.media import VideoMetadata
from pyrenees_selects.preeditor import PreEditor, ProjectOptions, SelectionDraft


class PreEditorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.editor = PreEditor(self.root / "selects.sqlite3")
        self.project = self.editor.create_project(
            ProjectOptions("Another trip", 90, "landscape", "A quiet two-minute travel film")
        )
        self.media = self.root / "media"
        (self.media / "day-two").mkdir(parents=True)
        (self.media / "first.mp4").write_bytes(b"first-source")
        (self.media / "day-two" / "second.mov").write_bytes(b"second-source")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def probe(path: Path) -> VideoMetadata:
        if path.name == "broken.mp4":
            raise RuntimeError("unreadable test source")
        return VideoMetadata(
            path=str(path.resolve()),
            filename=path.name,
            captured_at="2026-01-02T03:04:05+00:00",
            duration=20.0 if path.name in {"first.mp4", "renamed.mp4"} else 12.0,
            width=3840,
            height=2160,
            fps=30.0,
            codec="h264",
            size_bytes=path.stat().st_size,
        )

    def scan(self) -> list[dict]:
        self.editor.add_source_root(self.project["id"], self.media)
        return self.editor.scan(self.project["id"], probe=self.probe)["sources"]

    def test_recursive_scan_continues_after_a_bad_file(self) -> None:
        (self.media / "broken.mp4").write_bytes(b"broken")
        sources = self.scan()
        self.assertEqual(len(sources), 3)
        self.assertEqual({source["status"] for source in sources}, {"ready", "error"})
        self.assertEqual(
            next(source for source in sources if source["filename"] == "second.mov")["relative_path"],
            "day-two/second.mov",
        )

    def test_missing_media_is_offline_without_losing_selections(self) -> None:
        sources = self.scan()
        source = next(source for source in sources if source["filename"] == "first.mp4")
        selection = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 2, 8, decision="keep")
        )
        (self.media / "first.mp4").unlink()
        self.editor.scan(self.project["id"], probe=self.probe)
        self.assertEqual(self.editor.source(source["id"])["status"], "offline")
        self.assertEqual(self.editor.selection(selection["id"])["decision"], "keep")

    def test_renamed_media_keeps_its_source_and_selection_identity(self) -> None:
        sources = self.scan()
        source = next(source for source in sources if source["filename"] == "first.mp4")
        selection = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 1, 4, decision="keep")
        )
        (self.media / "first.mp4").rename(self.media / "renamed.mp4")
        self.editor.scan(self.project["id"], probe=self.probe)
        relinked = self.editor.source(source["id"])
        self.assertEqual(relinked["filename"], "renamed.mp4")
        self.assertEqual(relinked["status"], "ready")
        self.assertEqual(self.editor.selection(selection["id"])["source_id"], source["id"])

    def test_relink_rejects_a_different_file_with_the_same_size(self) -> None:
        source = next(item for item in self.scan() if item["filename"] == "first.mp4")
        replacement = self.root / "different.mp4"
        replacement.write_bytes(b"other-source")
        self.assertEqual(replacement.stat().st_size, (self.media / "first.mp4").stat().st_size)
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.editor.relink_source(source["id"], replacement, probe=self.probe)

    def test_multiple_ranges_comments_markers_and_validation(self) -> None:
        source = self.scan()[0]
        first = self.editor.create_selection(
            self.project["id"],
            SelectionDraft(source["id"], 1, 5, decision="keep", comment="Use the reaction"),
        )
        second = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 8, 11, decision="maybe")
        )
        self.editor.add_marker(first["id"], 3.5, "Cut after the turn")
        self.assertEqual(len(self.editor.selections(self.project["id"])), 2)
        self.assertEqual(self.editor.markers(first["id"])[0]["comment"], "Cut after the turn")
        self.assertNotEqual(first["id"], second["id"])
        with self.assertRaises(ValueError):
            self.editor.update_selection(second["id"], out_seconds=30)

    def test_project_settings_backup_and_selection_archive_are_safe(self) -> None:
        source = self.scan()[0]
        selection = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 1, 4, decision="keep")
        )
        version = self.editor.create_sequence(self.project["id"], "First cut", [selection["id"]])
        updated = self.editor.update_project(
            self.project["id"], name="A warmer cut", target_duration=None,
            orientation="portrait", ideal_clip_duration=5.5,
        )
        backup = self.editor.backup_database(self.root / "backups" / "selects.sqlite3")
        self.editor.archive_selection(selection["id"])
        self.assertEqual(updated["orientation"], "portrait")
        self.assertTrue(backup.is_file())
        self.assertEqual(self.editor.selections(self.project["id"]), [])
        self.assertEqual(self.editor.sequence_version(version["id"])["items"][0]["id"], selection["id"])

    def test_schema_upgrade_creates_a_recovery_backup(self) -> None:
        with self.editor.connection() as connection:
            connection.execute("UPDATE preeditor_schema SET version=1")
        migrated = PreEditor(self.root / "selects.sqlite3")
        self.assertEqual(migrated.project(self.project["id"])["name"], self.project["name"])
        self.assertEqual(len(list(self.root.glob("selects.schema-1.*.backup.sqlite3"))), 1)

    def test_sequence_revisions_are_immutable_and_leave_alternates_available(self) -> None:
        sources = self.scan()
        selections = [
            self.editor.create_selection(
                self.project["id"], SelectionDraft(source["id"], 0, min(4, source["duration"]), decision="keep")
            )
            for source in sources
        ]
        v1 = self.editor.create_sequence(
            self.project["id"], "First cut", [selections[0]["id"]], target_duration=30
        )
        v2 = self.editor.revise_sequence(
            v1["sequence_id"], [selections[1]["id"], selections[0]["id"]], note="Try alternate first"
        )
        self.assertEqual(v1["version"], 1)
        self.assertEqual(self.editor.sequence_version(v1["id"])["items"][0]["id"], selections[0]["id"])
        self.assertEqual(v2["version"], 2)
        self.assertEqual(v2["duration"], 8)

    def test_agent_context_is_path_free_and_proposals_require_approval(self) -> None:
        source = self.scan()[0]
        selection = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 1, 4, decision="keep")
        )
        context = self.editor.project_context(self.project["id"])
        rendered = str(context)
        self.assertNotIn(str(self.media), rendered)
        proposal = self.editor.create_proposal(
            self.project["id"],
            provider="codex",
            model="",
            kind="sequence",
            payload={"selection_ids": [selection["id"]]},
            explanation="A deliberately empty first pass",
        )
        self.assertEqual(proposal["status"], "pending")
        accepted = self.editor.decide_proposal(proposal["id"], "accepted")
        self.assertEqual(accepted["status"], "accepted")
        with self.assertRaises(KeyError):
            self.editor.decide_proposal(proposal["id"], "rejected")

    def test_applying_a_proposal_creates_a_version_only_after_approval(self) -> None:
        source = self.scan()[0]
        selection = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 1, 4, decision="keep")
        )
        proposal = self.editor.create_proposal(
            self.project["id"], provider="claude", model="", kind="sequence",
            payload={"selection_ids": [selection["id"]], "name": "Agent cut"},
        )
        self.assertEqual(self.editor.sequences(self.project["id"]), [])
        applied = self.editor.apply_proposal(proposal["id"])
        self.assertEqual(applied["proposal"]["status"], "accepted")
        self.assertEqual(applied["result"]["items"][0]["id"], selection["id"])
        self.assertEqual(len(self.editor.sequences(self.project["id"])), 1)

    def test_double_applying_a_proposal_creates_only_one_cut(self) -> None:
        source = self.scan()[0]
        selection = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 1, 4, decision="keep")
        )
        proposal = self.editor.create_proposal(
            self.project["id"], provider="test", model="", kind="sequence",
            payload={"selection_ids": [selection["id"]]},
        )
        results: list[object] = []

        def apply() -> None:
            try:
                results.append(self.editor.apply_proposal(proposal["id"]))
            except Exception as exc:
                results.append(exc)

        threads = [threading.Thread(target=apply) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(isinstance(item, dict) for item in results), 1)
        self.assertEqual(len(self.editor.sequences(self.project["id"])), 1)


if __name__ == "__main__":
    unittest.main()
