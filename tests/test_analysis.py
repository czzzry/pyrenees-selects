from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch

from pyrenees_selects.analysis import FRAME_BYTES, _frame_metrics, _window_score, analyze_video


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


if __name__ == "__main__":
    unittest.main()
