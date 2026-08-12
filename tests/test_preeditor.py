import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_new_project_defaults_are_a_120_second_landscape_brief(self) -> None:
        project = self.editor.create_project(ProjectOptions("Default brief"))
        self.assertEqual(project["target_duration_seconds"], 120)
        self.assertEqual(project["orientation"], "landscape")
        self.assertEqual(
            (project["shot_rhythm"], project["shot_min_seconds"], project["shot_max_seconds"]),
            ("balanced", 6, 9),
        )

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

    def test_preparation_revalidates_source_bytes_after_scan(self) -> None:
        source = next(item for item in self.scan() if item["filename"] == "first.mp4")
        (self.media / "first.mp4").write_bytes(b"changed-data")
        with patch("pyrenees_selects.preeditor.probe_video", side_effect=self.probe):
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                self.editor.assert_source_unchanged(source["id"], source["fingerprint"])

    def test_full_fingerprint_detects_same_size_middle_change(self) -> None:
        payload = bytearray(b"a" * 200_000)
        (self.media / "first.mp4").write_bytes(payload)
        source = next(item for item in self.scan() if item["filename"] == "first.mp4")
        payload[100_000] = ord("b")
        (self.media / "first.mp4").write_bytes(payload)
        with patch("pyrenees_selects.preeditor.probe_video", side_effect=self.probe):
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                self.editor.assert_source_unchanged(source["id"], source["fingerprint"])

    def test_scan_rejects_symlink_escape_from_registered_root(self) -> None:
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"outside-source")
        (self.media / "linked.mp4").symlink_to(outside)
        sources = self.scan()
        self.assertNotIn("linked.mp4", {item["filename"] for item in sources})

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
        clamped = self.editor.update_selection(second["id"], out_seconds=30)
        self.assertEqual(clamped["out_seconds"], source["duration"])

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

    def test_sequence_item_is_a_frozen_snapshot_after_selection_changes(self) -> None:
        source = self.scan()[0]
        selection = self.editor.create_selection(
            self.project["id"],
            SelectionDraft(source["id"], 1, 5, decision="keep", comment="Original note"),
        )
        v1 = self.editor.create_sequence(self.project["id"], "Frozen cut", [selection["id"]])
        self.editor.update_selection(
            selection["id"], in_seconds=3, out_seconds=9, comment="A later edit",
            treatment={"rotation": 90},
        )
        v2 = self.editor.latest_sequence_version(v1["sequence_id"])

        frozen = self.editor.sequence_version(v1["id"])["items"][0]
        current = self.editor.sequence_version(v2["id"])["items"][0]
        self.assertEqual((frozen["in_seconds"], frozen["out_seconds"], frozen["comment"]), (1, 5, "Original note"))
        self.assertEqual((current["in_seconds"], current["out_seconds"], current["comment"]), (3, 9, "A later edit"))
        self.assertEqual(frozen["treatment"], {})
        self.assertEqual(current["treatment"], {"rotation": 90})
        revisions = self.editor.selection_revisions(selection["id"])
        self.assertEqual([item["revision"] for item in revisions], [1, 2])
        self.assertEqual(json.loads(revisions[0]["snapshot_json"])["comment"], "Original note")

    def test_sequence_orientation_is_frozen_with_the_version(self) -> None:
        source = self.scan()[0]
        selection = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 1, 5, decision="keep")
        )
        landscape = self.editor.create_sequence(self.project["id"], "Frozen format", [selection["id"]])
        self.editor.update_project(self.project["id"], orientation="portrait")
        self.assertEqual(self.editor.sequence_version(landscape["id"])["orientation"], "landscape")
        portrait = self.editor.revise_sequence(landscape["sequence_id"], [selection["id"]])
        self.assertEqual(portrait["orientation"], "portrait")

    def test_canonical_selection_times_are_integer_microseconds(self) -> None:
        source = self.scan()[0]
        selection = self.editor.create_selection(
            self.project["id"], SelectionDraft(source["id"], 0.91, 2.09, decision="keep")
        )
        self.assertEqual((selection["in_us"], selection["out_us"]), (900_000, 2_100_000))
        self.assertEqual(selection["duration_us"], 1_200_000)

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
