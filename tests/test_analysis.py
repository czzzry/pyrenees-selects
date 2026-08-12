from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

from pyrenees_selects.analysis import (
    FRAME_BYTES,
    _frame_metrics,
    _window_score,
    analyze_video,
    candidates_from_metrics,
)


class SparseAnalysisTests(unittest.TestCase):
    def test_balanced_detailed_sustained_window_scores_well(self) -> None:
        strong = [(125.0, 20.0, 7.0)] * 4
        weak = [(245.0, 1.0, 0.1)] * 4
        strong_score, _ = _window_score(strong)
        weak_score, _ = _window_score(weak)
        self.assertGreater(strong_score, weak_score)

    def test_frame_metrics_detect_change(self) -> None:
        previous = bytes([20] * (160 * 90))
        current = bytes([100] * (160 * 90))
        mean, _gradient, motion = _frame_metrics(current, previous)
        self.assertEqual(mean, 100.0)
        self.assertGreater(motion, 70.0)

    def test_subsecond_video_still_yields_an_analysis_sample(self) -> None:
        class FakeProcess:
            def __init__(self, command: list[str]) -> None:
                video_filter = command[command.index("-vf") + 1]
                self.stdout = BytesIO(bytes([125]) * FRAME_BYTES if "round=up" in video_filter else b"")
                self.stderr = BytesIO()

            def poll(self) -> int:
                return 0

            def wait(self) -> int:
                return 0

            def kill(self) -> None:
                return None

        with patch("pyrenees_selects.analysis.subprocess.Popen", side_effect=lambda command, **_kwargs: FakeProcess(command)):
            result = analyze_video(Path("subsecond.mp4"), 0.665, ffmpeg="ffmpeg")

        self.assertEqual(result.start_seconds, 0.0)
        self.assertEqual(result.duration, 0.665)

    def test_two_good_phases_yield_separated_ranges(self) -> None:
        weak = (240.0, 1.0, 0.1)
        strong = (125.0, 24.0, 7.0)
        metrics = [weak] * 3 + [strong] * 4 + [weak] * 3 + [strong] * 4 + [weak]
        candidates = candidates_from_metrics(
            metrics,
            duration=30,
            budget_seconds=12,
            shot_min_seconds=6,
            shot_max_seconds=6,
        )
        self.assertEqual(len(candidates), 2)
        self.assertLess(candidates[0].out_us + 2_000_000, candidates[1].in_us + 1)

    def test_audio_activity_only_changes_audio_enabled_ranking(self) -> None:
        visual = [(125.0, 20.0, 7.0)] * 8
        audio = [0.9] * 4 + [0.0] * 4
        visual_only = candidates_from_metrics(
            visual, duration=16, budget_seconds=6, shot_min_seconds=6, shot_max_seconds=6,
            audio=audio, audio_preference="visual",
        )
        audio_aware = candidates_from_metrics(
            visual, duration=16, budget_seconds=6, shot_min_seconds=6, shot_max_seconds=6,
            audio=audio, audio_preference="speech_and_distinctive",
        )
        self.assertEqual(visual_only[0].in_us, 0)
        self.assertEqual(audio_aware[0].in_us, 0)
        self.assertNotIn("audio_activity", visual_only[0].components)
        self.assertIn("audio_activity", audio_aware[0].components)
        self.assertNotIn("speech", audio_aware[0].rationale.lower())


if __name__ == "__main__":
    unittest.main()
