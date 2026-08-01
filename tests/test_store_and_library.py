import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.library import PROJECT_ID, scan_project
from pyrenees_selects.edit_plan import EDIT_PLAN_ITEMS, STORYBOARD_VARIANTS
from pyrenees_selects.media import VideoMetadata
from pyrenees_selects.store import Store
from pyrenees_selects.treatment_plan import LONG_ROUGH_CUT_ADDITIONS, LONG_ROUGH_CUT_ORDER


class StoreAndLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "footage"
        self.source.mkdir()
        self.store = Store(self.root / "app.sqlite3")
        self.store.upsert_project(PROJECT_ID, "Pyrenees 2024", str(self.source))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_scan_persists_top_level_media_and_candidates(self) -> None:
        for name in ("DJI_20240609090000_0001_D.MP4", "DJI_20240719090000_0002_D.MP4"):
            (self.source / name).write_bytes(b"placeholder")

        def fake_probe(path: Path) -> VideoMetadata:
            return VideoMetadata(
                path=str(path.resolve()), filename=path.name, captured_at="2024-06-09T09:00:00+00:00",
                duration=100.0, width=3840, height=2160, fps=29.97, codec="hevc", size_bytes=path.stat().st_size,
            )

        result = scan_project(self.store, PROJECT_ID, probe=fake_probe)
        self.assertEqual(result["summary"]["media_count"], 2)
        self.assertEqual(result["summary"]["decisions"]["pending"]["count"], 2)
        candidate = self.store.next_candidate(PROJECT_ID)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["decision"], "pending")
        self.assertEqual(result["summary"]["analyzed_count"], 0)

        self.store.update_candidate_analysis(candidate["id"], 12.0, 8.0, "Balanced exposure.", 0.82, 1)
        analyzed = self.store.candidate(candidate["id"])
        self.assertEqual(analyzed["start_seconds"], 12.0)
        self.assertEqual(analyzed["analysis_version"], 1)
        self.assertEqual(self.store.summary(PROJECT_ID)["analyzed_count"], 1)

    def test_settings_persist_the_active_project(self) -> None:
        self.store.set_setting("active_project_id", PROJECT_ID)
        self.assertEqual(self.store.setting("active_project_id"), PROJECT_ID)

    def test_decision_persists_and_advances_queue(self) -> None:
        source = self.source / "DJI_20240609090000_0001_D.MP4"
        source.write_bytes(b"placeholder")

        def fake_probe(path: Path) -> VideoMetadata:
            return VideoMetadata(str(path.resolve()), path.name, "2024-06-09T09:00:00+00:00", 20, 1920, 1080, 25, "hevc", 11)

        scan_project(self.store, PROJECT_ID, probe=fake_probe)
        candidate = self.store.next_candidate(PROJECT_ID)
        decided = self.store.decide(candidate["id"], "keep", "opening")
        self.assertEqual(decided["decision"], "keep")
        self.assertEqual(decided["story_role"], "opening")
        self.assertIsNone(self.store.next_candidate(PROJECT_ID))

    def test_completed_screening_is_snapshotted_before_refinement(self) -> None:
        source = self.source / "DJI_20240609090000_0001_D.MP4"
        source.write_bytes(b"placeholder")

        def fake_probe(path: Path) -> VideoMetadata:
            return VideoMetadata(str(path.resolve()), path.name, "2024-06-09T09:00:00+00:00", 20, 3840, 2160, 25, "hevc", 11)

        scan_project(self.store, PROJECT_ID, probe=fake_probe)
        candidate = self.store.next_candidate(PROJECT_ID)
        self.store.decide(candidate["id"], "keep", "opening")

        selected = self.store.refinement_candidates(PROJECT_ID)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["screening_decision"], "keep")
        self.assertEqual(selected[0]["screening_story_role"], "opening")

        saved = self.store.save_refinement(candidate["id"], "Hold longer on the reveal.", 12.5, reviewed=True)
        self.assertEqual(saved["note"], "Hold longer on the reveal.")
        self.assertEqual(saved["note_anchor_seconds"], 12.5)
        self.assertIsNotNone(saved["reviewed_at"])
        self.assertEqual(self.store.refinement_summary(PROJECT_ID), {"total": 1, "reviewed": 1, "noted": 1})

        self.store.decide(candidate["id"], "skip")
        preserved = self.store.refinement_candidates(PROJECT_ID)[0]
        self.assertEqual(preserved["screening_decision"], "keep")
        self.assertEqual(preserved["decision"], "skip")

    def test_first_pass_comment_is_saved_before_decision_and_carried_into_refinement(self) -> None:
        source = self.source / "DJI_20240609090000_0001_D.MP4"
        source.write_bytes(b"placeholder")

        def fake_probe(path: Path) -> VideoMetadata:
            return VideoMetadata(str(path.resolve()), path.name, "2024-06-09T09:00:00+00:00", 20, 3840, 2160, 25, "hevc", 11)

        scan_project(self.store, PROJECT_ID, probe=fake_probe)
        candidate = self.store.next_candidate(PROJECT_ID)
        saved = self.store.save_candidate_note(candidate["id"], "  Start earlier and hold longer.  ")

        self.assertEqual(saved["note"], "Start earlier and hold longer.")
        self.assertEqual(self.store.next_candidate(PROJECT_ID)["note"], "Start earlier and hold longer.")

        self.store.decide(candidate["id"], "keep")
        selected = self.store.refinement_candidates(PROJECT_ID)
        self.assertEqual(selected[0]["note"], "Start earlier and hold longer.")

    def test_screening_snapshot_waits_until_every_candidate_is_decided(self) -> None:
        for name in ("DJI_20240609090000_0001_D.MP4", "DJI_20240610090000_0002_D.MP4"):
            (self.source / name).write_bytes(b"placeholder")

        def fake_probe(path: Path) -> VideoMetadata:
            return VideoMetadata(str(path.resolve()), path.name, path.stem[4:18], 20, 3840, 2160, 25, "hevc", 11)

        scan_project(self.store, PROJECT_ID, probe=fake_probe)
        first = self.store.next_candidate(PROJECT_ID)
        self.store.decide(first["id"], "keep")
        self.assertEqual(self.store.refinement_summary(PROJECT_ID)["total"], 0)

        second = self.store.next_candidate(PROJECT_ID)
        self.store.decide(second["id"], "maybe")
        self.assertEqual(self.store.refinement_summary(PROJECT_ID)["total"], 2)

    def test_pyrenees_storyboard_seeds_without_changing_screening_or_notes(self) -> None:
        for number in range(1, 80):
            (self.source / f"DJI_20240609{number:06d}_D.MP4").write_bytes(b"placeholder")

        def fake_probe(path: Path) -> VideoMetadata:
            return VideoMetadata(
                str(path.resolve()), path.name, "2024-06-09T09:00:00+00:00",
                600, 3840, 2160, 29.97, "hevc", path.stat().st_size,
            )

        scan_project(self.store, PROJECT_ID, probe=fake_probe)
        candidates = self.store.project_candidates(PROJECT_ID)
        self.assertEqual([candidate["id"] for candidate in candidates], list(range(1, 80)))
        for candidate in candidates:
            decision = "keep" if candidate["id"] % 2 else "maybe"
            self.store.decide(candidate["id"], decision)
        self.store.save_refinement(5, "Keep my exact note.", reviewed=True)

        reopened = Store(self.root / "app.sqlite3")
        self.assertEqual(reopened.summary(PROJECT_ID)["decisions"]["keep"]["count"], 40)
        self.assertEqual(reopened.summary(PROJECT_ID)["decisions"]["maybe"]["count"], 39)
        notes = {candidate["id"]: candidate["note"] for candidate in reopened.refinement_candidates(PROJECT_ID)}
        self.assertEqual(notes[5], "Keep my exact note.")
        self.assertEqual(len(EDIT_PLAN_ITEMS), 52)
        self.assertEqual(reopened.edit_plan_item(78)["recommendation"], "deferred")
        self.assertEqual(reopened.edit_plan_item(78)["proposed_start_seconds"], 59.2)
        self.assertEqual(reopened.edit_plan_item(78)["proposed_duration"], 2.536)
        self.assertIn("Signature moment", reopened.edit_plan_item(78)["treatment"])
        self.assertIn("Signature moment", reopened.edit_plan_item(74)["treatment"])
        self.assertEqual(
            {variant: len(reopened.storyboard_items(PROJECT_ID, variant)) for variant in STORYBOARD_VARIANTS},
            {90: 15, 120: 20, 180: 33},
        )
        two_minute = reopened.storyboard_items(PROJECT_ID, 120)
        self.assertNotIn(78, [item["candidate_id"] for item in two_minute])

        first = two_minute[0]
        saved_storyboard_note = reopened.save_storyboard_note(
            first["storyboard_item_id"], "  This preview still feels too fast.  "
        )
        self.assertEqual(saved_storyboard_note["storyboard_note"], "This preview still feels too fast.")
        noted = reopened.storyboard_items(PROJECT_ID, 120)[0]
        self.assertEqual(noted["storyboard_note"], "This preview still feels too fast.")
        self.assertEqual(noted["note"], "Keep my exact note.")

        reopened.review_storyboard_item(first["storyboard_item_id"], "replace", 4)
        replaced = reopened.storyboard_items(PROJECT_ID, 120)[0]
        self.assertEqual(replaced["candidate_id"], 4)
        self.assertEqual(replaced["storyboard_note"], "This preview still feels too fast.")
        reopened.review_storyboard_item(first["storyboard_item_id"], "approve")
        self.assertEqual(reopened.storyboard_items(PROJECT_ID, 120)[0]["candidate_id"], 4)
        reopened.review_storyboard_item(first["storyboard_item_id"], "restore")
        restored = reopened.storyboard_items(PROJECT_ID, 120)[0]
        self.assertEqual(restored["candidate_id"], 5)
        self.assertEqual(restored["review_state"], "approved")

        addition_ids = {recipe.candidate_id for recipe in LONG_ROUGH_CUT_ADDITIONS}
        hybrid_order = tuple(candidate_id for candidate_id in LONG_ROUGH_CUT_ORDER if candidate_id in addition_ids)
        hybrid = reopened.hybrid_review_items(PROJECT_ID, hybrid_order)
        self.assertEqual([item["candidate_id"] for item in hybrid], list(hybrid_order))
        self.assertEqual(reopened.hybrid_review_summary(PROJECT_ID, hybrid_order), {
            "total": 13, "pending": 13, "add": 0, "long_only": 0, "unsure": 0,
        })
        reopened.save_hybrid_review(hybrid[0]["storyboard_item_id"], "add")
        reopened.save_hybrid_review(hybrid[1]["storyboard_item_id"], "long_only")
        reopened.save_hybrid_review(hybrid[2]["storyboard_item_id"], "unsure")
        self.assertEqual(reopened.hybrid_review_summary(PROJECT_ID, hybrid_order), {
            "total": 13, "pending": 10, "add": 1, "long_only": 1, "unsure": 1,
        })
        self.assertEqual(reopened.storyboard_items(PROJECT_ID, 120)[0]["review_state"], "approved")
        self.assertEqual(reopened.summary(PROJECT_ID)["decisions"]["keep"]["count"], 40)
        self.assertEqual(
            {candidate["id"]: candidate["note"] for candidate in reopened.refinement_candidates(PROJECT_ID)}[5],
            "Keep my exact note.",
        )

    def test_edit_plan_ranges_and_variants_are_internally_consistent(self) -> None:
        self.assertEqual(set(STORYBOARD_VARIANTS), {90, 120, 180})
        self.assertEqual(len(EDIT_PLAN_ITEMS), 52)
        for candidate_id, item in EDIT_PLAN_ITEMS.items():
            self.assertGreaterEqual(candidate_id, 1)
            self.assertGreaterEqual(item["start"], 0)
            self.assertGreater(item["duration"], 0)
            self.assertIn(item["recommendation"], {"core", "alternate", "drop", "deferred"})
        for variant, items in STORYBOARD_VARIANTS.items():
            candidate_ids = [candidate_id for candidate_id, _ in items]
            self.assertEqual(len(candidate_ids), len(set(candidate_ids)))
            self.assertNotIn(78, candidate_ids)
            self.assertTrue(set(candidate_ids).issubset(EDIT_PLAN_ITEMS))
            self.assertTrue(all(target > 0 for _, target in items))


if __name__ == "__main__":
    unittest.main()
