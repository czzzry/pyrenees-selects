import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyrenees_selects.media import (
    VideoMetadata,
    _atempo_filter_chain,
    cache_key,
    candidate_range,
    render_review_clip,
    top_level_videos,
    treatment_filter_chain,
)
from pyrenees_selects.phone_treatment_plan import PHONE_TREATMENTS
from pyrenees_selects.integrated_plan import (
    DRONE_HYBRID_ORDER,
    INTEGRATED_DRONE_PHONE_ORDER,
    PHONE_APPROVED_ORDER,
)
from pyrenees_selects.treatment_plan import (
    HYBRID_COMMENT_TREATMENTS,
    LONG_ROUGH_CUT_ADDITIONS,
    LONG_ROUGH_CUT_ORDER,
    TREATED_LONG_ROUGH_CUT,
    TREATED_ROUGH_CUT,
)


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

    @patch("pyrenees_selects.media.platform.system", return_value="Darwin")
    def test_review_render_uses_the_mac_hardware_decoder(self, _system: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            destination = root / "review.mp4"
            source.write_bytes(b"source")

            def fake_run(command: list[str], **_kwargs: object) -> None:
                Path(command[-1]).write_bytes(b"preview")

            with patch("pyrenees_selects.media.subprocess.run", side_effect=fake_run) as run:
                render_review_clip(source, destination, 2.0, 4.0, ffmpeg="ffmpeg")

            command = run.call_args.args[0]
            self.assertIn("videotoolbox", command)
            self.assertEqual(destination.read_bytes(), b"preview")

    def test_treatment_filter_chain_applies_stabilization_speed_and_interpolation(self) -> None:
        filter_chain = treatment_filter_chain(
            0.6,
            crop_scale=0.88,
            contrast=1.05,
            motion_interpolation=True,
            stabilization_transform=Path("/tmp/example transform.trf"),
        )
        self.assertIn("crop=", filter_chain)
        self.assertIn("vidstabtransform=", filter_chain)
        self.assertIn("minterpolate=", filter_chain)
        self.assertIn("setpts=(PTS-STARTPTS)/0.600000", filter_chain)

    def test_treatment_filter_chain_can_rotate_and_ease_a_zoom(self) -> None:
        filter_chain = treatment_filter_chain(
            2.0,
            rotate_counterclockwise=True,
            zoom_strength=0.6,
            zoom_center_y=0.32,
            output_duration=6.0,
        )
        self.assertIn("transpose=2", filter_chain)
        self.assertIn("zoompan=", filter_chain)
        self.assertIn("sin(PI*on/149)", filter_chain)

    def test_audio_retiming_uses_valid_chained_atempo_factors(self) -> None:
        self.assertEqual(_atempo_filter_chain(1.0), [])
        self.assertEqual(_atempo_filter_chain(0.3125), ["atempo=0.500000", "atempo=0.625000"])
        self.assertEqual(_atempo_filter_chain(5.0), ["atempo=2.000000", "atempo=2.000000", "atempo=1.250000"])

    def test_phone_treatment_plan_covers_the_approved_twenty_shots(self) -> None:
        candidate_ids = [treatment.candidate_id for treatment in PHONE_TREATMENTS]
        self.assertEqual(
            candidate_ids,
            [82, 83, 85, 88, 92, 94, 97, 98, 102, 103, 106, 110, 111, 113, 116, 119, 124, 130, 134, 138],
        )
        self.assertTrue(next(item for item in PHONE_TREATMENTS if item.candidate_id == 130).rotate_counterclockwise)
        self.assertEqual(next(item for item in PHONE_TREATMENTS if item.candidate_id == 138).audio_playback_rate, 1.0)

    def test_integrated_plan_splices_every_phone_shot_into_the_drone_hybrid(self) -> None:
        drone_ids = tuple(
            candidate_id for origin, candidate_id in INTEGRATED_DRONE_PHONE_ORDER if origin == "drone"
        )
        phone_ids = tuple(
            candidate_id for origin, candidate_id in INTEGRATED_DRONE_PHONE_ORDER if origin == "phone"
        )
        self.assertEqual(drone_ids, DRONE_HYBRID_ORDER)
        self.assertEqual(phone_ids, PHONE_APPROVED_ORDER)
        self.assertEqual(len(INTEGRATED_DRONE_PHONE_ORDER), 50)
        first_later_drone = INTEGRATED_DRONE_PHONE_ORDER.index(("drone", 29))
        self.assertTrue(
            all(origin == "drone" for origin, _candidate_id in INTEGRATED_DRONE_PHONE_ORDER[first_later_drone:])
        )

    def test_treated_rough_cut_covers_every_two_minute_shot_and_slows_candidate_74_to_five_seconds(self) -> None:
        candidate_ids = [recipe.candidate_id for recipe in TREATED_ROUGH_CUT]
        self.assertEqual(len(candidate_ids), 20)
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))
        slowed_peak = next(recipe for recipe in TREATED_ROUGH_CUT if recipe.candidate_id == 74)
        self.assertAlmostEqual(slowed_peak.output_duration, 5.0)
        self.assertTrue(slowed_peak.motion_interpolation)

    def test_long_rough_cut_reuses_the_north_star_and_adds_the_extended_bird_slot(self) -> None:
        self.assertEqual(len(LONG_ROUGH_CUT_ORDER), 34)
        self.assertEqual(len(set(LONG_ROUGH_CUT_ORDER)), 34)
        self.assertEqual(LONG_ROUGH_CUT_ORDER[-2:], (78, 79))
        self.assertEqual(len(LONG_ROUGH_CUT_ADDITIONS), 13)
        self.assertEqual(len(TREATED_LONG_ROUGH_CUT), 33)
        self.assertEqual(
            [recipe.candidate_id for recipe in TREATED_LONG_ROUGH_CUT],
            [candidate_id for candidate_id in LONG_ROUGH_CUT_ORDER if candidate_id != 78],
        )
        self.assertAlmostEqual(sum(recipe.output_duration for recipe in TREATED_ROUGH_CUT), 152.2)
        self.assertAlmostEqual(sum(recipe.output_duration for recipe in LONG_ROUGH_CUT_ADDITIONS), 67.0)
        self.assertAlmostEqual(sum(recipe.output_duration for recipe in TREATED_LONG_ROUGH_CUT) + 7.96, 227.16)

    def test_hybrid_comment_treatments_trim_the_trail_and_slow_the_lake_zoom(self) -> None:
        by_candidate = {recipe.candidate_id: recipe for recipe in HYBRID_COMMENT_TREATMENTS}
        self.assertEqual(set(by_candidate), {37, 52})
        self.assertAlmostEqual(by_candidate[37].output_duration, 5.0)
        self.assertTrue(by_candidate[37].stabilize)
        self.assertAlmostEqual(by_candidate[52].playback_rate, 0.8)
        self.assertAlmostEqual(by_candidate[52].output_duration, 6.25)
        self.assertTrue(by_candidate[52].stabilize)
        self.assertTrue(by_candidate[52].motion_interpolation)


if __name__ == "__main__":
    unittest.main()
