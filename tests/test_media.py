import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.media import VideoMetadata, cache_key, candidate_range, top_level_videos


class MediaTests(unittest.TestCase):
    def test_candidate_range_keeps_a_sustained_window_inside_source(self) -> None:
        start, duration = candidate_range(100.0)
        self.assertEqual(duration, 8.0)
        self.assertGreaterEqual(start, 0)
        self.assertLessEqual(start + duration, 100.0)

    def test_candidate_range_uses_entire_short_source(self) -> None:
        self.assertEqual(candidate_range(3.5), (0.0, 3.5))

    def test_top_level_videos_excludes_nested_and_non_video_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "A.MP4").write_bytes(b"")
            (root / "B.mov").write_bytes(b"")
            (root / "photo.jpg").write_bytes(b"")
            nested = root / "canada"
            nested.mkdir()
            (nested / "C.MP4").write_bytes(b"")
            self.assertEqual([path.name for path in top_level_videos(root)], ["A.MP4", "B.mov"])

    def test_cache_key_changes_when_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"first")
            first = cache_key(source, 2.0, 8.0, "review")
            source.write_bytes(b"second version")
            second = cache_key(source, 2.0, 8.0, "review")
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
