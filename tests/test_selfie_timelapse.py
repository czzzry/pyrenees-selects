import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pyrenees_selects.selfie_timelapse import (
    alignment_transform,
    build_manifest,
    encode_diagnostic_video,
    ensure_output_outside_source,
    probe_video,
    select_pilot,
    soft_lock_transform,
)


class SelfieTimelapseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "photos"
        self.source.mkdir()
        self.inventory = self.root / "face-inventory.tsv"
        self.state = self.root / "selfie-review.json"
        self.names = [
            "PXL_20240612_092047035.jpg",
            "PXL_20240613_063111726.jpg",
            "PXL_20240614_094156592.jpg",
        ]
        for index, name in enumerate(self.names):
            Image.new("RGB", (120 + index * 10, 160), (40 + index * 20, 80, 120)).save(self.source / name)
        self.inventory.write_text(
            "filename\tstatus\tface_count\tlargest_area\tx\ty\twidth\theight\n"
            f"{self.names[2]}\tlikely_selfie\t1\t0.04\t0.02\t0.10\t0.20\t0.20\n"
            f"{self.names[0]}\tlikely_selfie\t1\t0.08\t0.30\t0.20\t0.25\t0.30\n"
            f"{self.names[1]}\tlikely_selfie\t1\t0.12\t0.65\t0.30\t0.30\t0.35\n",
            encoding="utf-8",
        )
        reviews = {
            self.names[0]: {"decision": "include", "comment": ""},
            self.names[1]: {"decision": "include", "comment": "Check my eyes"},
            self.names[2]: {"decision": "maybe", "comment": ""},
        }
        self.state.write_text(
            json.dumps({"version": 1, "source_dir": str(self.source), "reviews": reviews}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_manifest_is_chronological_hashed_and_complete(self) -> None:
        manifest = build_manifest(self.source, self.inventory, self.state)
        self.assertEqual(manifest["photo_count"], 3)
        self.assertEqual([record["filename"] for record in manifest["photos"]], self.names)
        self.assertTrue(all(len(record["sha256"]) == 64 for record in manifest["photos"]))
        self.assertEqual(manifest["photos"][1]["comment"], "Check my eyes")

    def test_pilot_keeps_comments_and_non_include_decisions(self) -> None:
        manifest = build_manifest(self.source, self.inventory, self.state, include_hashes=False)
        geometry = {
            self.names[0]: {"cx": 0.4, "cy": 0.4, "area": 0.08, "edge": 0.2},
            self.names[1]: {"cx": 0.8, "cy": 0.5, "area": 0.12, "edge": 0.02},
            self.names[2]: {"cx": 0.1, "cy": 0.2, "area": 0.04, "edge": 0.01},
        }
        selected = select_pilot(manifest["photos"], geometry, limit=3)
        by_name = {record["filename"]: record for record in selected}
        self.assertIn("saved comment", by_name[self.names[1]]["pilot_reasons"])
        self.assertIn("decision: maybe", by_name[self.names[2]]["pilot_reasons"])

    def test_alignment_places_eye_midpoint_and_distance_at_targets(self) -> None:
        transform = alignment_transform(
            1000,
            800,
            {"x": 0.4, "y": 0.3},
            {"x": 0.6, "y": 0.3},
            canvas=1000,
            target_x=0.5,
            target_y=0.4,
            target_eye_distance=0.1,
        )
        self.assertAlmostEqual(transform.scale, 0.5)
        self.assertAlmostEqual(transform.source_eye_midpoint_x * transform.scale + transform.translate_x, 500)
        self.assertAlmostEqual(transform.source_eye_midpoint_y * transform.scale + transform.translate_y, 400)
        self.assertAlmostEqual(transform.source_eye_distance * transform.scale, 100)

    def test_soft_lock_fills_when_dead_zone_can_be_respected_without_excessive_zoom(self) -> None:
        transform, mode = soft_lock_transform(
            1200,
            1600,
            {"x": 0.42, "y": 0.38},
            {"x": 0.58, "y": 0.38},
            canvas=1000,
            target_x=0.5,
            target_y=0.4,
            target_eye_distance=0.11,
        )
        self.assertEqual(mode, "fill-first")
        self.assertLessEqual(transform.target_eye_distance, 180)
        self.assertAlmostEqual(transform.source_eye_midpoint_x * transform.scale + transform.translate_x, 500)

    def test_soft_lock_routes_extreme_edge_face_to_background_extension(self) -> None:
        transform, mode = soft_lock_transform(
            1600,
            1200,
            {"x": 0.02, "y": 0.38},
            {"x": 0.10, "y": 0.38},
            canvas=1000,
            target_x=0.5,
            target_y=0.4,
            target_eye_distance=0.11,
        )
        self.assertEqual(mode, "background-extension")
        self.assertAlmostEqual(transform.target_eye_midpoint_x, 500)

    def test_output_folder_cannot_be_inside_originals(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the original"):
            ensure_output_outside_source(self.source / "pilot", self.source)
        allowed = ensure_output_outside_source(self.root / "analysis", self.source)
        self.assertEqual(allowed, (self.root / "analysis").resolve())

    def test_diagnostic_encoder_holds_each_photo_for_three_video_frames(self) -> None:
        frames = self.root / "frames"
        frames.mkdir()
        Image.new("RGB", (64, 64), "red").save(frames / "frame-0001.jpg")
        Image.new("RGB", (64, 64), "blue").save(frames / "frame-0002.jpg")
        destination = self.root / "diagnostic.mp4"
        encode_diagnostic_video(frames, destination, image_count=2)
        probe = probe_video(destination)
        stream = probe["streams"][0]
        self.assertEqual(stream["width"], 64)
        self.assertEqual(stream["height"], 64)
        self.assertEqual(stream["r_frame_rate"], "24/1")
        self.assertEqual(int(stream["nb_frames"]), 6)


if __name__ == "__main__":
    unittest.main()
