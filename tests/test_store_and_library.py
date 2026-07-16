import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.library import PROJECT_ID, scan_project
from pyrenees_selects.media import VideoMetadata
from pyrenees_selects.store import Store


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


if __name__ == "__main__":
    unittest.main()
