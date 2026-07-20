import tempfile
import unittest
from pathlib import Path

from scripts.run_synthetic_demo import build_clip_command


class SyntheticDemoTests(unittest.TestCase):
    def test_demo_command_uses_generated_test_pattern_and_safe_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "sample.mp4"

            command = build_clip_command(
                "/usr/local/bin/ffmpeg",
                destination,
                "65",
                "2024-06-24T10:30:00Z",
            )

            self.assertIn("testsrc2=size=640x360:rate=24", command)
            self.assertIn("hue=h=65", command)
            self.assertIn("creation_time=2024-06-24T10:30:00Z", command)
            self.assertEqual(command[-1], str(destination))


if __name__ == "__main__":
    unittest.main()
