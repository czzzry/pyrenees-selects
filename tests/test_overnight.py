from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from pyrenees_selects.analysis import AnalyzedCandidate
from pyrenees_selects.media import MediaToolError, render_candidate_sample, require_media_tools
from pyrenees_selects.overnight import OvernightRunManager
from pyrenees_selects.preeditor import PreEditor, ProjectOptions


class FakePower:
    def __init__(self) -> None:
        self.acquired = 0
        self.released = 0

    def acquire(self):
        self.acquired += 1
        return object(), ""

    def release(self, _handle):
        self.released += 1


class OvernightRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.editor = PreEditor(self.root / "selects.sqlite3")
        self.footage = self.root / "footage"
        self.footage.mkdir()
        self.source = self.footage / "neutral.mp4"
        ffmpeg, _ = require_media_tools()
        subprocess.run(
            [
                ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=4",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4", "-shortest",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-y", str(self.source),
            ],
            check=True,
            capture_output=True,
        )
        self.project = self.editor.create_project(ProjectOptions(
            "Neutral overnight", target_duration=10, orientation="landscape", shot_rhythm="custom",
            shot_min_seconds=1, shot_max_seconds=2, candidate_breadth="focused",
        ))
        self.editor.add_source_root(self.project["id"], self.footage)
        self.editor.scan(self.project["id"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def analyzer(*_args, **_kwargs):
        return [
            AnalyzedCandidate(
                1_000_000, 2_000_000, 0.91,
                {"detail": 0.9, "movement": 0.8},
                "Suggested from measured signals: strong visible detail and steady scenic movement.",
            )
        ]

    @staticmethod
    def proxy(source: Path, destination: Path, **_kwargs):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    @staticmethod
    def sample(source: Path, destination: Path, **kwargs):
        return render_candidate_sample(source, destination, **kwargs)

    def manager(self, *, power=None, proxy=None) -> OvernightRunManager:
        return OvernightRunManager(
            self.editor, self.root / "cache", analyzer=self.analyzer,
            proxy_renderer=proxy or self.proxy, sample_renderer=self.sample,
            power_provider=power or FakePower(),
        )

    @staticmethod
    def wait_for(manager: OvernightRunManager, run_id: str, states: set[str]) -> dict:
        deadline = time.time() + 25
        while time.time() < deadline:
            run = manager.store.run(run_id)
            if run["state"] in states:
                return run
            time.sleep(0.03)
        raise AssertionError(f"Run did not reach {states}")

    def test_plan_run_candidate_review_and_power_lifecycle(self) -> None:
        power = FakePower()
        manager = self.manager(power=power)
        plan = manager.plan(self.project["id"], prevent_sleep=True)
        self.assertEqual(plan["state"], "planned")
        self.assertEqual(plan["plan"]["provenance"], "calculated")
        self.assertEqual(
            set(plan["plan"]["inventory"]),
            {"ready", "unique_readable", "duplicates", "portrait", "silent", "vfr", "very_short", "broken", "offline", "unsupported"},
        )
        manager.start(plan["id"])
        completed = self.wait_for(manager, plan["id"], {"completed", "failed"})
        self.assertEqual(completed["state"], "completed")
        self.assertEqual(completed["progress_fraction"], 1.0)
        self.assertEqual(len(completed["candidates"]), 1)
        self.assertEqual((power.acquired, power.released), (1, 1))

        manager.store.set_run(plan["id"], "paused", warning="The selected cache ran out of space.")
        moved = manager.relocate_cache(plan["id"], self.root / "alternate-cache")
        self.assertEqual(Path(moved["cache_path"]), (self.root / "alternate-cache").resolve())
        self.assertTrue(manager.candidate_sample(completed["candidates"][0]["id"]).is_file())
        manager.store.set_run(plan["id"], "completed", ended=True)

        candidate = completed["candidates"][0]
        reviewed = manager.store.review_candidate(candidate["id"], {
            "decision": "keep", "comment": "Hold through the turn", "story_role": "opening",
            "audio_intent": "preserve", "in_us": 900_000, "out_us": 2_100_000,
        })
        self.assertEqual(reviewed["review_state"], "kept")
        self.assertEqual((reviewed["generated_in_us"], reviewed["generated_out_us"]), (1_000_000, 2_000_000))
        self.assertEqual((reviewed["in_us"], reviewed["out_us"]), (875_000, 2_125_000))
        selection = self.editor.selection(reviewed["linked_selection_id"])
        self.assertEqual(selection["comment"], "Hold through the turn")
        self.assertAlmostEqual(selection["in_seconds"], 0.875, places=6)
        self.assertAlmostEqual(selection["out_seconds"], 2.125, places=6)
        self.assertEqual(len(self.editor.selection_revisions(selection["id"])), 1)
        skipped = manager.store.review_candidate(candidate["id"], {"decision": "skip"})
        self.assertEqual(skipped["review_state"], "skipped")
        self.assertIsNone(skipped["linked_selection_id"])
        self.assertEqual(self.editor.selections(self.project["id"]), [])

    def test_run_queue_never_expands_a_small_budget_across_every_source(self) -> None:
        self.editor.update_project(
            self.project["id"], target_duration_seconds=10, shot_rhythm="energetic",
            candidate_breadth="focused",
        )
        original = self.editor.sources(self.project["id"])[0]
        with self.editor.connection() as connection:
            for index in range(20):
                values = dict(original)
                values.update({
                    "id": f"source_extra_{index}", "relative_path": f"extra-{index}.mp4",
                    "fingerprint": f"fingerprint-extra-{index}", "filename": f"extra-{index}.mp4",
                })
                columns = list(values)
                connection.execute(
                    f"INSERT INTO preeditor_sources({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
                    [values[column] for column in columns],
                )
        run = self.manager().plan(self.project["id"], prevent_sleep=False)
        self.assertLessEqual(len(run["sources"]), run["plan"]["maximum_candidate_count"])
        self.assertTrue(all(source["source_id"] for source in run["sources"]))

    def test_pause_is_durable_and_releases_power(self) -> None:
        power = FakePower()
        entered = False

        def blocking_proxy(_source: Path, destination: Path, *, cancel=None, **_kwargs):
            nonlocal entered
            entered = True
            destination.parent.mkdir(parents=True, exist_ok=True)
            while not cancel.is_set():
                time.sleep(0.01)
            raise InterruptedError("paused")

        manager = self.manager(power=power, proxy=blocking_proxy)
        plan = manager.plan(self.project["id"], prevent_sleep=True)
        manager.start(plan["id"])
        deadline = time.time() + 2
        while not entered and time.time() < deadline:
            time.sleep(0.01)
        manager.pause(plan["id"])
        paused = self.wait_for(manager, plan["id"], {"paused"})
        self.assertEqual(paused["sources"][0]["state"], "pending")
        self.assertEqual(power.released, 1)

        with self.editor.connection() as connection:
            connection.execute("UPDATE preeditor_analysis_runs SET state='running' WHERE id=?", (plan["id"],))
        recovered = self.manager().store.run(plan["id"])
        self.assertEqual(recovered["state"], "paused")

    def test_restart_invalidates_corrupt_completed_sample(self) -> None:
        manager = self.manager()
        plan = manager.plan(self.project["id"], prevent_sleep=False)
        manager.start(plan["id"])
        completed = self.wait_for(manager, plan["id"], {"completed"})
        sample = manager.candidate_sample(completed["candidates"][0]["id"])
        self.assertIsNotNone(sample)
        sample.write_bytes(b"not media")

        recovered = self.manager().store.run(plan["id"])
        self.assertEqual(recovered["state"], "paused")
        self.assertEqual(recovered["sources"][0]["state"], "pending")
        self.assertFalse(recovered["candidates"][0]["sample_ready"])
        self.assertIn("validation", recovered["warning"].lower())

    def test_restart_rejects_readable_same_duration_sample_from_wrong_range(self) -> None:
        manager = self.manager()
        plan = manager.plan(self.project["id"], prevent_sleep=False)
        manager.start(plan["id"])
        completed = self.wait_for(manager, plan["id"], {"completed"})
        sample = manager.candidate_sample(completed["candidates"][0]["id"])
        self.assertIsNotNone(sample)
        ffmpeg, _ = require_media_tools()
        replacement = sample.with_name("wrong-range.mp4")
        subprocess.run(
            [ffmpeg, "-v", "error", "-f", "lavfi", "-i",
             "color=c=red:size=320x180:rate=24:duration=1", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-y", str(replacement)],
            check=True, capture_output=True,
        )
        replacement.replace(sample)
        recovered = self.manager().store.run(plan["id"])
        self.assertEqual(recovered["state"], "paused")
        self.assertFalse(recovered["candidates"][0]["sample_ready"])

    def test_low_disk_plan_is_truthful_and_blocks_start(self) -> None:
        usage = shutil._ntuple_diskusage(total=10_000, used=9_500, free=500)
        with patch("pyrenees_selects.overnight.shutil.disk_usage", return_value=usage):
            manager = self.manager()
            plan = manager.plan(self.project["id"], prevent_sleep=False)
        self.assertFalse(plan["plan"]["disk"]["can_start"])
        self.assertGreater(plan["plan"]["disk"]["shortfall_bytes"], 0)
        with patch("pyrenees_selects.overnight.shutil.disk_usage", return_value=usage):
            with self.assertRaisesRegex(ValueError, "enough free space"):
                manager.start(plan["id"])

    def test_cancel_media_failure_disk_failure_and_shutdown_release_power(self) -> None:
        def blocking_proxy(_source: Path, _destination: Path, *, cancel=None, **_kwargs):
            while not cancel.is_set():
                time.sleep(0.01)
            raise InterruptedError("stopped")

        for action in ("cancel", "shutdown"):
            with self.subTest(action=action):
                power = FakePower(); manager = self.manager(power=power, proxy=blocking_proxy)
                plan = manager.plan(self.project["id"], prevent_sleep=True); manager.start(plan["id"])
                deadline = time.time() + 2
                while power.acquired == 0 and time.time() < deadline: time.sleep(0.01)
                if action == "cancel":
                    manager.cancel(plan["id"])
                    final = self.wait_for(manager, plan["id"], {"cancelled"})
                    self.assertEqual(final["state"], "cancelled")
                    self.assertTrue(all(source["state"] == "cancelled" for source in final["sources"]))
                else:
                    manager.shutdown()
                    final = self.wait_for(manager, plan["id"], {"paused"})
                    self.assertEqual(final["state"], "paused")
                self.assertEqual(power.released, 1)

        def disk_full(*_args, **_kwargs):
            raise MediaToolError("ffmpeg failed: No space left on device")

        power = FakePower(); manager = self.manager(power=power, proxy=disk_full)
        plan = manager.plan(self.project["id"], prevent_sleep=True); manager.start(plan["id"])
        paused = self.wait_for(manager, plan["id"], {"paused"})
        self.assertIn("space", paused["warning"].lower())
        self.assertEqual(power.released, 1)

        def bad_analysis(*_args, **_kwargs):
            raise RuntimeError("decoder failed")

        power = FakePower()
        manager = OvernightRunManager(
            self.editor, self.root / "failed-cache", analyzer=bad_analysis,
            proxy_renderer=self.proxy, sample_renderer=self.sample, power_provider=power,
        )
        plan = manager.plan(self.project["id"], prevent_sleep=True); manager.start(plan["id"])
        failed = self.wait_for(manager, plan["id"], {"failed"})
        self.assertIn("decoder failed", failed["sources"][0]["error"])
        self.assertEqual(power.released, 1)

    def test_real_ffmpeg_stderr_is_recognized_as_disk_full(self) -> None:
        process_error = subprocess.CalledProcessError(
            1, ["ffmpeg"], stderr="muxer: No space left on device"
        )
        wrapped = MediaToolError("Could not create a review copy")
        wrapped.__cause__ = process_error
        self.assertTrue(OvernightRunManager._looks_like_disk_full(process_error))
        self.assertTrue(OvernightRunManager._looks_like_disk_full(wrapped))

    def test_retry_removes_failed_task_credit_before_reprocessing(self) -> None:
        entered = False

        def bad_analysis(*_args, **_kwargs):
            raise RuntimeError("temporary decoder failure")

        manager = OvernightRunManager(
            self.editor, self.root / "retry-cache", analyzer=bad_analysis,
            proxy_renderer=self.proxy, sample_renderer=self.sample, power_provider=FakePower(),
        )
        plan = manager.plan(self.project["id"], prevent_sleep=False)
        manager.start(plan["id"])
        failed = self.wait_for(manager, plan["id"], {"failed"})
        self.assertEqual(failed["progress_fraction"], 1.0)

        def blocking_analysis(*args, cancel=None, **kwargs):
            nonlocal entered
            entered = True
            while not cancel.is_set():
                time.sleep(0.01)
            raise InterruptedError("paused")

        manager.analyzer = blocking_analysis
        retried = manager.retry(plan["id"], [failed["sources"][0]["source_id"]])
        self.assertLess(retried["progress_fraction"], 1.0)
        deadline = time.time() + 2
        while not entered and time.time() < deadline: time.sleep(0.01)
        manager.pause(plan["id"])
        self.wait_for(manager, plan["id"], {"paused"})

    def test_elapsed_time_advances_during_first_source(self) -> None:
        def blocking_proxy(_source: Path, _destination: Path, *, cancel=None, **_kwargs):
            while not cancel.is_set():
                time.sleep(0.01)
            raise InterruptedError("paused")

        manager = self.manager(proxy=blocking_proxy)
        plan = manager.plan(self.project["id"], prevent_sleep=False)
        manager.start(plan["id"])
        time.sleep(0.15)
        self.assertGreater(manager.store.run(plan["id"])["elapsed_seconds"], 0.1)
        manager.pause(plan["id"])
        self.wait_for(manager, plan["id"], {"paused"})


if __name__ == "__main__":
    unittest.main()
