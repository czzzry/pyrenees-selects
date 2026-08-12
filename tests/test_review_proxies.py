import tempfile
import time
import unittest
from pathlib import Path

from pyrenees_selects.media import VideoMetadata
from pyrenees_selects.preeditor import PreEditor, ProjectOptions
from pyrenees_selects.review_proxies import ReviewProxyManager


class ReviewProxyManagerTests(unittest.TestCase):
    def test_queue_is_resumable_from_completed_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            footage = root / "footage"
            footage.mkdir()
            for name in ("one.mp4", "two.mp4"):
                (footage / name).write_bytes(name.encode())
            editor = PreEditor(root / "selects.sqlite3")
            project = editor.create_project(ProjectOptions("Neutral project"))
            editor.add_source_root(project["id"], footage)

            def probe(path: Path) -> VideoMetadata:
                return VideoMetadata(str(path.resolve()), path.name, "2026-01-01T00:00:00+00:00", 12, 1920, 1080, 24, "h264", path.stat().st_size, True)

            editor.scan(project["id"], probe=probe)
            rendered: list[str] = []

            def renderer(source: Path, destination: Path) -> Path:
                rendered.append(source.name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"proxy")
                return destination

            manager = ReviewProxyManager(editor, root / "cache", renderer=renderer)
            manager.start(project["id"])
            deadline = time.monotonic() + 2
            while manager.status(project["id"])["state"] == "running" and time.monotonic() < deadline:
                time.sleep(0.01)

            status = manager.status(project["id"])
            self.assertEqual(status["state"], "ready")
            self.assertEqual(status["ready"], 2)
            self.assertEqual(sorted(rendered), ["one.mp4", "two.mp4"])

            resumed = ReviewProxyManager(editor, root / "cache", renderer=renderer)
            self.assertEqual(resumed.status(project["id"])["ready"], 2)
            resumed.start(project["id"])
            deadline = time.monotonic() + 2
            while resumed.status(project["id"])["state"] == "running" and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(rendered), 2)


if __name__ == "__main__":
    unittest.main()
