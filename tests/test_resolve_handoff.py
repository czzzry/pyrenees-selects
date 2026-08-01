import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from pyrenees_selects.resolve_handoff import SourceMedia, build_fcpxml, fcpx_time, frame_duration


class ResolveHandoffTests(unittest.TestCase):
    def test_frame_rates_use_exact_rational_durations(self) -> None:
        self.assertEqual(fcpx_time(frame_duration(29.97)), "1001/30000s")
        self.assertEqual(fcpx_time(frame_duration(25.0)), "1/25s")

    def test_handoff_links_thirty_clips_and_preserves_bird_master(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {}
            items = []
            for position in range(1, 31):
                candidate_id = 78 if position == 29 else position
                path = root / f"source-{candidate_id}.mp4"
                path.write_bytes(b"video")
                if candidate_id != 78:
                    sources[candidate_id] = SourceMedia(
                        candidate_id=candidate_id,
                        path=path,
                        duration=100.0,
                        width=3840,
                        height=2160,
                        fps=25.0 if position % 6 == 0 else 29.97,
                    )
                    items.append({
                        "position": position,
                        "candidate_id": candidate_id,
                        "source_start": 5.0,
                        "source_duration": 5.0,
                        "output_duration": 6.25 if position == 18 else 5.0,
                        "playback_rate": 0.8 if position == 18 else 1.0,
                        "stabilize": position == 18,
                        "crop_scale": 0.88 if position == 16 else 1.0,
                        "contrast": 1.0,
                        "motion_interpolation": position == 18,
                        "rationale": "Test treatment",
                        "original_note": "",
                        "hybrid_note": "",
                    })
                else:
                    items.append({
                        "position": position,
                        "candidate_id": 78,
                        "signature_moment": True,
                        "output_duration": 7.96,
                        "rationale": "Extended bird",
                    })
            bird_path = root / "bird-master.mp4"
            bird_path.write_bytes(b"bird")
            bird = SourceMedia(78, bird_path, 7.974633, 1920, 1080, 29.97)

            xml, manifest = build_fcpxml(items, sources, bird)
            tree = ET.fromstring(xml.split("<!DOCTYPE fcpxml>\n", 1)[1])
            library = tree.find("./library")
            self.assertIsNotNone(library)
            clips = tree.findall("./library/event/project/sequence/spine/asset-clip")
            self.assertEqual(len(clips), 30)
            self.assertEqual(manifest["item_count"], 30)
            self.assertEqual(manifest["original_4k_item_count"], 29)
            self.assertEqual(manifest["bird_master_item_count"], 1)
            bird_asset = next(
                asset for asset in tree.findall("./resources/asset")
                if asset.attrib.get("name") == "bird-master.mp4"
            )
            self.assertEqual(bird_asset.find("media-rep").attrib["src"], bird_path.resolve().as_uri())
            slowed = clips[17]
            time_map = slowed.find("timeMap")
            self.assertIsNotNone(time_map)
            self.assertEqual(time_map.attrib["frameSampling"], "optical-flow")
            time_points = time_map.findall("timept")
            self.assertEqual(time_points[0].attrib, {
                "time": "0s",
                "value": "5s",
                "interp": "linear",
            })
            self.assertEqual(time_points[1].attrib, {
                "time": "187187/30000s",
                "value": "10s",
                "interp": "linear",
            })
            cropped = clips[15]
            self.assertEqual(
                cropped.find("adjust-transform").attrib["scale"],
                "1.1364 1.1364",
            )

    def test_integrated_handoff_can_be_4k_and_keep_phone_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            phone_path = root / "phone.mp4"
            drone_path = root / "drone.mp4"
            bird_path = root / "bird-master.mp4"
            for path in (phone_path, drone_path, bird_path):
                path.write_bytes(b"video")
            sources = {
                82: SourceMedia(82, phone_path, 20.0, 3840, 2160, 29.97),
                5: SourceMedia(5, drone_path, 20.0, 3840, 2160, 29.97),
            }
            bird = SourceMedia(78, bird_path, 8.0, 1920, 1080, 29.97)
            items = [
                {
                    "position": 1,
                    "candidate_id": 82,
                    "source_start": 1.0,
                    "source_duration": 4.0,
                    "output_duration": 2.0,
                    "playback_rate": 2.0,
                    "crop_scale": 1.0,
                    "contrast": 1.0,
                    "saturation": 1.0,
                    "rationale": "Phone moment",
                },
                {
                    "position": 2,
                    "candidate_id": 5,
                    "source_start": 3.0,
                    "source_duration": 5.0,
                    "output_duration": 5.0,
                    "playback_rate": 1.0,
                    "crop_scale": 1.0,
                    "contrast": 1.0,
                    "saturation": 1.0,
                    "rationale": "Drone moment",
                },
            ]

            xml, manifest = build_fcpxml(
                items,
                sources,
                bird,
                expected_item_count=2,
                timeline_width=3840,
                timeline_height=2160,
                audio_candidate_ids=frozenset({82}),
            )
            tree = ET.fromstring(xml.split("<!DOCTYPE fcpxml>\n", 1)[1])
            timeline_format = tree.find("./resources/format[@id='r1']")
            self.assertEqual(timeline_format.attrib["width"], "3840")
            self.assertEqual(timeline_format.attrib["height"], "2160")
            phone_asset = next(
                asset for asset in tree.findall("./resources/asset")
                if asset.attrib.get("name") == "phone.mp4"
            )
            self.assertEqual(phone_asset.attrib["hasAudio"], "1")
            self.assertEqual(phone_asset.attrib["audioSources"], "1")
            clips = tree.findall("./library/event/project/sequence/spine/asset-clip")
            self.assertEqual(clips[0].attrib["audioRole"], "dialogue")
            self.assertEqual(clips[0].find("timeMap").attrib["preservesPitch"], "1")
            self.assertNotIn("audioRole", clips[1].attrib)
            self.assertEqual(manifest["timeline_resolution"], "3840x2160")
            self.assertEqual(manifest["source_audio_item_count"], 1)


if __name__ == "__main__":
    unittest.main()
