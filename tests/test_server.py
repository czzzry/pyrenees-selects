import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyrenees_selects.server import create_local_server, parse_byte_range


class ServerTests(unittest.TestCase):
    def test_open_ended_byte_range(self) -> None:
        self.assertEqual(parse_byte_range("bytes=100-", 1000), (100, 999))

    def test_bounded_byte_range_is_clamped(self) -> None:
        self.assertEqual(parse_byte_range("bytes=100-2000", 1000), (100, 999))

    def test_suffix_byte_range(self) -> None:
        self.assertEqual(parse_byte_range("bytes=-100", 1000), (900, 999))

    def test_invalid_byte_range(self) -> None:
        self.assertIsNone(parse_byte_range("bytes=1000-1001", 1000))

    @patch("pyrenees_selects.server.require_media_tools", return_value=("ffmpeg", "ffprobe"))
    def test_local_server_can_choose_an_ephemeral_port(self, _tools: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server, _application = create_local_server(data_dir=Path(directory), port=0)
            try:
                self.assertGreater(server.server_address[1], 0)
                self.assertEqual(server.server_address[0], "127.0.0.1")
            finally:
                server.server_close()


if __name__ == "__main__":
    unittest.main()
