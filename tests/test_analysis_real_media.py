from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.analysis import analyze_video_candidates
from pyrenees_selects.media import require_media_tools


class RealMediaAnalysisOracleTests(unittest.TestCase):
    def test_known_temporal_phases_surface_two_separated_sustained_windows(self) -> None:
        ffmpeg, _ = require_media_tools()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "temporal-oracle.mp4"
            command = [
                ffmpeg, "-v", "error",
                "-f", "lavfi", "-i", "color=c=0x101010:s=320x180:r=24:d=6",
                "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=8",
                "-f", "lavfi", "-i", "color=black:s=320x180:r=24:d=6,negate=enable='lt(mod(t,3),1.5)'",
                "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=8",
                "-f", "lavfi", "-i", "color=c=0x777777:s=320x180:r=24:d=2",
                "-filter_complex", "[0:v][1:v][2:v][3:v][4:v]concat=n=5:v=1:a=0,format=yuv420p[v]",
                "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast", "-y", str(source),
            ]
            subprocess.run(command, check=True, capture_output=True, timeout=90)
            candidates = analyze_video_candidates(
                source, 30, budget_seconds=12, shot_min_seconds=6, shot_max_seconds=6,
                audio_preference="visual", ffmpeg=ffmpeg,
            )

        self.assertEqual(len(candidates), 2)
        self.assertLessEqual(abs(candidates[0].in_us / 1_000_000 - 6), 2)
        self.assertGreaterEqual(candidates[1].in_us - candidates[0].out_us, 2_000_000)
        for candidate in candidates:
            self.assertNotIn("speech", candidate.rationale.lower())


if __name__ == "__main__":
    unittest.main()
