import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from pyrenees_selects.sequence_export import build_fcpxml


class SequenceExportTests(unittest.TestCase):
    def test_fcpxml_links_original_ranges_and_carries_editorial_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original & one.mp4"
            source.write_bytes(b"source")
            version = {
                "sequence_name": "A first cut",
                "items": [{
                    "id": "selection_one", "filename": source.name, "current_path": str(source),
                    "source_status": "ready", "source_duration": 20.0, "in_seconds": 2.0,
                    "out_seconds": 7.0, "duration": 5.0, "fps": 30.0, "comment": "Keep the answer",
                    "story_role": "opening", "audio_intent": "speech",
                }],
            }
            xml, manifest = build_fcpxml(version, project_name="Another project")
            parsed = ET.fromstring(xml.split("<!DOCTYPE fcpxml>\n", 1)[1])
            representation = parsed.find("./resources/asset/media-rep")
            clip = parsed.find("./library/event/project/sequence/spine/asset-clip")
            self.assertEqual(representation.attrib["src"], source.resolve().as_uri())
            self.assertEqual(clip.attrib["start"], "2s")
            self.assertIn("Keep the answer", clip.find("note").text)
            self.assertAlmostEqual(manifest["duration"], 5.005, places=3)
            self.assertEqual(manifest["timeline"]["width"], 3840)

    def test_portrait_export_uses_a_portrait_4k_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "vertical.mov"
            source.write_bytes(b"source")
            version = {"items": [{
                "id": "selection_vertical", "filename": source.name, "current_path": str(source),
                "source_status": "ready", "source_duration": 4.0, "in_seconds": 0.0,
                "out_seconds": 4.0, "duration": 4.0, "fps": 30.0, "has_audio": False,
            }]}
            xml, manifest = build_fcpxml(version, project_name="Portrait", orientation="portrait")
            parsed = ET.fromstring(xml.split("<!DOCTYPE fcpxml>\n", 1)[1])
            timeline_format = parsed.find("./resources/format")
            asset = parsed.find("./resources/asset")
            self.assertEqual((timeline_format.attrib["width"], timeline_format.attrib["height"]), ("2160", "3840"))
            self.assertNotIn("hasAudio", asset.attrib)
            self.assertEqual(manifest["timeline"]["height"], 3840)

    def test_export_refuses_offline_sources(self):
        version = {"items": [{"filename": "gone.mov", "source_status": "offline"}]}
        with self.assertRaisesRegex(ValueError, "offline"):
            build_fcpxml(version, project_name="Another project")


if __name__ == "__main__":
    unittest.main()
