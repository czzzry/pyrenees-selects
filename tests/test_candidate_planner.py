from __future__ import annotations

import unittest

from pyrenees_selects.candidate_planner import build_candidate_plan, estimate_artifacts


def source(identifier: str, duration: float, *, fingerprint: str | None = None, status: str = "ready") -> dict:
    return {
        "id": identifier,
        "fingerprint": fingerprint or f"fingerprint-{identifier}",
        "duration": duration,
        "relative_path": f"day/{identifier}.mp4",
        "captured_at": f"2026-01-01T00:00:{len(identifier):02d}+00:00",
        "status": status,
    }


class CandidatePlannerTests(unittest.TestCase):
    def test_contract_golden_counts(self) -> None:
        cases = (
            ({"target_duration_seconds": 240, "shot_rhythm": "balanced", "candidate_breadth": "generous"}, 600, (480, 54, 80)),
            ({"target_duration_seconds": 60, "shot_rhythm": "energetic", "candidate_breadth": "focused"}, 100, (75, 15, 25)),
            ({"target_duration_seconds": 120, "shot_rhythm": "observational", "candidate_breadth": "broad"}, 90, (90, 6, 9)),
        )
        for brief, footage, expected in cases:
            with self.subTest(brief=brief):
                plan = build_candidate_plan(brief, [source("one", footage)])
                self.assertEqual(
                    (plan.candidate_duration_target, plan.minimum_candidate_count, plan.maximum_candidate_count),
                    expected,
                )

    def test_valid_subsecond_source_yields_one_opportunity(self) -> None:
        plan = build_candidate_plan(
            {"target_duration_seconds": 10, "shot_rhythm": "balanced", "candidate_breadth": "generous"},
            [source("tiny", 0.665)],
        )
        self.assertEqual(plan.candidate_duration_target, 0.665)
        self.assertEqual((plan.minimum_candidate_count, plan.maximum_candidate_count), (1, 1))
        self.assertEqual(plan.sources[0].maximum_windows, 1)

    def test_offline_and_duplicate_sources_do_not_inflate_budget(self) -> None:
        plan = build_candidate_plan(
            {"target_duration_seconds": 60, "shot_rhythm": "balanced", "candidate_breadth": "generous"},
            [
                source("original", 40, fingerprint="same"),
                source("duplicate", 40, fingerprint="same"),
                source("offline", 80, status="offline"),
            ],
        )
        self.assertEqual(plan.readable_source_duration, 40)
        self.assertEqual(plan.duplicate_source_ids, ("duplicate",))
        self.assertAlmostEqual(sum(item.budget_seconds for item in plan.sources), 40)

    def test_custom_bounds_and_disk_estimate_are_explicit(self) -> None:
        plan = build_candidate_plan(
            {
                "target_duration_seconds": 120,
                "shot_rhythm": "custom",
                "shot_min_seconds": 4,
                "shot_max_seconds": 7,
                "candidate_breadth": "broad",
            },
            [source("a", 120), source("b", 240)],
        )
        estimate = estimate_artifacts(plan)
        self.assertEqual((plan.minimum_candidate_count, plan.maximum_candidate_count), (52, 90))
        self.assertEqual(estimate["provenance"], "calculated")
        self.assertEqual(estimate["required_free_bytes"], estimate["estimated_artifact_bytes"] + estimate["safety_reserve_bytes"])

    def test_missing_target_and_invalid_ranges_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "target film duration"):
            build_candidate_plan({}, [source("a", 20)])
        with self.assertRaisesRegex(ValueError, "between 1 and 60"):
            build_candidate_plan(
                {"target_duration_seconds": 60, "shot_rhythm": "custom", "shot_min_seconds": 10, "shot_max_seconds": 4},
                [source("a", 20)],
            )

    def test_small_budget_is_not_fragmented_across_every_source(self) -> None:
        plan = build_candidate_plan(
            {"target_duration_seconds": 10, "shot_rhythm": "energetic", "candidate_breadth": "focused"},
            [source(f"clip-{index:02d}", 30 + index) for index in range(20)],
        )
        planned_windows = sum(item.maximum_windows for item in plan.sources)
        active_sources = [item for item in plan.sources if item.budget_seconds > 0]
        self.assertLessEqual(planned_windows, plan.maximum_candidate_count)
        self.assertEqual(len(active_sources), plan.maximum_candidate_count)
        self.assertTrue(all(item.maximum_windows == 1 for item in active_sources))
        self.assertEqual(active_sources[0].source_id, "clip-00")
        self.assertEqual(active_sources[-1].source_id, "clip-19")

    def test_custom_minimum_cannot_overproduce_the_total_budget(self) -> None:
        plan = build_candidate_plan(
            {
                "target_duration_seconds": 10,
                "shot_rhythm": "custom",
                "shot_min_seconds": 60,
                "shot_max_seconds": 60,
                "candidate_breadth": "focused",
            },
            [source("long", 120)],
        )
        self.assertEqual(plan.candidate_duration_target, 12.5)
        self.assertEqual((plan.minimum_candidate_count, plan.maximum_candidate_count), (0, 0))
        self.assertEqual(sum(item.maximum_windows for item in plan.sources), 0)
        self.assertEqual(sum(item.budget_seconds for item in plan.sources), 0)


if __name__ == "__main__":
    unittest.main()
