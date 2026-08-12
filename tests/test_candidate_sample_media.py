from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.media import probe_video, render_candidate_sample, require_media_tools


class CandidateSampleMediaTests(unittest.TestCase):
    def test_exact_sample_is_validated_and_keeps_source_audio(self) -> None:
        ffmpeg, ffprobe = require_media_tools()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            sample = root / "candidate.mp4"
            subprocess.run(
                [
                    ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=3",
                    "-f", "lavfi", "-i", "sine=frequency=550:sample_rate=48000:duration=3", "-shortest",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-y", str(source),
                ],
                check=True, capture_output=True, timeout=60,
            )
            path, manifest = render_candidate_sample(
                source, sample, in_us=1_000_000, out_us=2_000_000,
                source_fps=24, has_audio=True, ffmpeg=ffmpeg, ffprobe=ffprobe,
            )
            metadata = probe_video(path, ffprobe=ffprobe)

        self.assertTrue(metadata.has_audio)
        self.assertAlmostEqual(metadata.duration, 1.0, delta=1 / 24)
        self.assertEqual((manifest["source_in_us"], manifest["source_out_us"]), (1_000_000, 2_000_000))
        self.assertLessEqual(abs(manifest["output_duration_us"] - 1_000_000), round(1_000_000 / 24))


if __name__ == "__main__":
    unittest.main()
