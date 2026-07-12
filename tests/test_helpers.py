import tempfile
import unittest
from pathlib import Path

from diagnostics import latest_performance_report_text
from music import is_supported_audio
from processor import export_remote_job_package


class HelperTests(unittest.TestCase):
    def test_audio_extension_check_is_case_insensitive(self) -> None:
        self.assertTrue(is_supported_audio(Path("soundtrack.MP3")))
        self.assertFalse(is_supported_audio(Path("notes.txt")))

    def test_latest_performance_report_returns_empty_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(latest_performance_report_text(Path(directory)), "")

    def test_remote_package_contains_only_handoff_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "clip.mp4"
            source.write_bytes(b"sample")
            requirements = root / "requirements.txt"
            requirements.write_text("streamlit>=1.34\n", encoding="utf-8")

            paths = export_remote_job_package(
                root / "package",
                {"render_mode": "preview"},
                [{"path": str(source), "filename": source.name, "include": True}],
                requirements,
            )

            self.assertEqual(set(paths), {"job_config", "manifest", "environment", "readme"})
            self.assertTrue(all(path.exists() for path in paths.values()))
            self.assertFalse((root / "package" / source.name).exists())


if __name__ == "__main__":
    unittest.main()
