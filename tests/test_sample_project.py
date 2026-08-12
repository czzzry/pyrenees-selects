import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.media import VideoMetadata
from pyrenees_selects.preeditor import PreEditor
from pyrenees_selects.sample_project import SAMPLE_NAME, ensure_sample_project


class SampleProjectTests(unittest.TestCase):
    def test_sample_project_reaches_a_first_sequence_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            editor = PreEditor(root / "selects.sqlite3")
            generated = 0

            def generator(destination: Path) -> list[Path]:
                nonlocal generated
                generated += 1
                destination.mkdir(parents=True, exist_ok=True)
                paths = [destination / name for name in ("morning-light.mp4", "coast-path.mp4", "train-arrival.mp4")]
                for path in paths:
                    path.write_bytes(path.name.encode())
                return paths

            def probe(path: Path) -> VideoMetadata:
                return VideoMetadata(str(path.resolve()), path.name, "2026-01-01T00:00:00+00:00", 12, 1280, 720, 24, "h264", path.stat().st_size, True)

            project = ensure_sample_project(editor, root, generator=generator, probe=probe)
            again = ensure_sample_project(editor, root, generator=generator, probe=probe)

            self.assertEqual(project["name"], SAMPLE_NAME)
            self.assertEqual(again["id"], project["id"])
            self.assertEqual(generated, 1)
            self.assertEqual(len(editor.sources(project["id"])), 3)
            self.assertEqual(len(editor.selections(project["id"])), 2)
            versions = editor.sequences(project["id"])
            self.assertEqual(len(versions), 1)
            self.assertEqual(len(editor.latest_sequence_version(versions[0]["id"])["items"]), 2)


if __name__ == "__main__":
    unittest.main()
