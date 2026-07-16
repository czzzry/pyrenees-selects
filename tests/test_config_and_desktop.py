import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyrenees_selects.config import AppPaths
from pyrenees_selects.desktop import SingleInstance
from pyrenees_selects.media import require_media_tools


class DesktopPackagingTests(unittest.TestCase):
    def test_resourcepath_supplies_frozen_static_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory)
            (resources / "static").mkdir()
            with patch.dict(os.environ, {"RESOURCEPATH": str(resources)}):
                paths = AppPaths.build(resources / "data")
            self.assertEqual(paths.static, (resources / "static").resolve())

    def test_bundled_media_tools_take_priority_over_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binary_dir = Path(directory)
            for name in ("ffmpeg", "ffprobe"):
                tool = binary_dir / name
                tool.touch(mode=0o755)
            with patch.dict(os.environ, {"PYRENEES_SELECTS_MEDIA_BIN_DIR": str(binary_dir)}):
                self.assertEqual(
                    require_media_tools(),
                    (str((binary_dir / "ffmpeg").resolve()), str((binary_dir / "ffprobe").resolve())),
                )

    def test_only_one_desktop_instance_holds_the_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "app.lock"
            first = SingleInstance(lock_path)
            second = SingleInstance(lock_path)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()


if __name__ == "__main__":
    unittest.main()
