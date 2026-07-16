import unittest

from pyrenees_selects.analysis import _frame_metrics, _window_score


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


if __name__ == "__main__":
    unittest.main()
