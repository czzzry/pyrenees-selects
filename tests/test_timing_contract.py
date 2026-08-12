from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.media import (
    frame_signature,
    probe_video,
    render_candidate_sample,
    require_media_tools,
    signature_hamming_distance,
)
from pyrenees_selects.preeditor import PreEditor, ProjectOptions, SelectionDraft
from pyrenees_selects.sequence_export import build_fcpxml, render_preview


class TimingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.ffmpeg, self.ffprobe = require_media_tools()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _frame_count(self, path: Path) -> int:
        result = subprocess.run(
            [self.ffprobe, "-v", "error", "-count_packets", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_packets", "-of", "json", str(path)],
            check=True, capture_output=True, text=True,
        )
        return int(json.loads(result.stdout)["streams"][0]["nb_read_packets"])

    def test_cfr_sample_has_inclusive_first_and_exclusive_end_frame(self) -> None:
        source = self.root / "cfr.mp4"
        subprocess.run(
            [self.ffmpeg, "-v", "error", "-f", "lavfi", "-i",
             "nullsrc=s=320x180:r=10:d=3,geq=lum='mod(X+Y+N*25,256)':cb='128':cr='128'",
             "-c:v", "libx264", "-g", "10",
             "-pix_fmt", "yuv420p", "-y", str(source)],
            check=True, capture_output=True,
        )
        sample, artifact = render_candidate_sample(
            source, self.root / "sample.mp4", in_us=900_000, out_us=2_100_000,
            source_fps=10, has_audio=False,
        )
        self.assertEqual(self._frame_count(sample), 12)
        self.assertEqual((artifact["source_in_us"], artifact["source_out_us"]), (900_000, 2_100_000))
        self.assertLessEqual(abs(artifact["output_duration_us"] - 1_200_000), 100_000)
        self.assertLessEqual(
            signature_hamming_distance(
                frame_signature(source, in_us=900_000), frame_signature(sample, in_us=0)
            ),
            0.22,
        )

        editor = PreEditor(self.root / "cfr.sqlite3")
        project = editor.create_project(ProjectOptions("CFR oracle", 10, "landscape"))
        editor.add_source_root(project["id"], self.root, recursive=False)
        scanned = editor.scan(project["id"])
        source_row = next(item for item in scanned["sources"] if item["filename"] == "cfr.mp4")
        selection = editor.create_selection(
            project["id"], SelectionDraft(source_row["id"], 0.9, 2.1, decision="keep")
        )
        version = editor.create_sequence(project["id"], "CFR oracle", [selection["id"]])
        preview = render_preview(version, self.root / "cfr-preview.mp4")
        xml, manifest = build_fcpxml(version, project_name="CFR oracle")
        self.assertEqual((selection["in_us"], selection["out_us"]), (900_000, 2_100_000))
        self.assertIn('start="9/10s"', xml)
        self.assertIn('duration="6/5s"', xml)
        self.assertEqual(
            (manifest["items"][0]["source_in_us"], manifest["items"][0]["source_out_us"]),
            (900_000, 2_100_000),
        )
        self.assertLessEqual(
            signature_hamming_distance(
                frame_signature(source, in_us=900_000), frame_signature(preview, in_us=0)
            ),
            0.22,
        )

    def test_frozen_portrait_orientation_controls_preview_dimensions(self) -> None:
        source = self.root / "portrait-source.mp4"
        subprocess.run(
            [self.ffmpeg, "-v", "error", "-f", "lavfi", "-i",
             "testsrc2=size=180x320:rate=10:duration=2", "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-y", str(source)],
            check=True, capture_output=True,
        )
        editor = PreEditor(self.root / "portrait.sqlite3")
        project = editor.create_project(ProjectOptions("Portrait oracle", 10, "portrait"))
        editor.add_source_root(project["id"], self.root, recursive=False)
        scanned = editor.scan(project["id"])
        row = next(item for item in scanned["sources"] if item["filename"] == source.name)
        selection = editor.create_selection(
            project["id"], SelectionDraft(row["id"], 0, 1, decision="keep")
        )
        version = editor.create_sequence(project["id"], "Portrait", [selection["id"]])
        preview = probe_video(render_preview(version, self.root / "portrait-preview.mp4"))
        self.assertEqual((preview.width, preview.height), (480, 854))

    def test_real_vfr_selection_sample_preview_and_handoff_keep_microseconds(self) -> None:
        source = self.root / "vfr.mp4"
        subprocess.run(
            [self.ffmpeg, "-v", "error",
             "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10:duration=1",
             "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=1",
             "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
             "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(source)],
            check=True, capture_output=True,
        )
        metadata = probe_video(source)
        self.assertTrue(metadata.is_vfr)

        editor = PreEditor(self.root / "selects.sqlite3")
        project = editor.create_project(ProjectOptions("VFR timing", 10, "landscape"))
        editor.add_source_root(project["id"], self.root, recursive=False)
        scanned = editor.scan(project["id"])
        source_row = next(item for item in scanned["sources"] if item["filename"] == "vfr.mp4")
        selection = editor.create_selection(
            project["id"], SelectionDraft(source_row["id"], 0.2, 1.8, decision="keep")
        )
        self.assertEqual((selection["in_us"], selection["out_us"]), (200_000, 1_800_000))
        version = editor.create_sequence(project["id"], "VFR cut", [selection["id"]])

        sample, artifact = render_candidate_sample(
            source, self.root / "vfr-sample.mp4", in_us=selection["in_us"], out_us=selection["out_us"],
            source_fps=float(source_row["fps"]), has_audio=False, is_vfr=True,
        )
        preview = render_preview(version, self.root / "vfr-preview.mp4")
        _, manifest = build_fcpxml(version, project_name="VFR timing")
        expected = selection["duration_us"] / 1_000_000
        self.assertLessEqual(abs(probe_video(sample).duration - expected), 0.05)
        self.assertLessEqual(abs(probe_video(preview).duration - expected), 0.05)
        self.assertEqual((artifact["source_in_us"], artifact["source_out_us"]), (200_000, 1_800_000))
        self.assertEqual(
            (manifest["items"][0]["source_in_us"], manifest["items"][0]["source_out_us"]),
            (200_000, 1_800_000),
        )


if __name__ == "__main__":
    unittest.main()
