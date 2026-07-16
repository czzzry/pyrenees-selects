import unittest

from pyrenees_selects.server import parse_byte_range


class ServerTests(unittest.TestCase):
    def test_open_ended_byte_range(self) -> None:
        self.assertEqual(parse_byte_range("bytes=100-", 1000), (100, 999))

    def test_bounded_byte_range_is_clamped(self) -> None:
        self.assertEqual(parse_byte_range("bytes=100-2000", 1000), (100, 999))

    def test_suffix_byte_range(self) -> None:
        self.assertEqual(parse_byte_range("bytes=-100", 1000), (900, 999))

    def test_invalid_byte_range(self) -> None:
        self.assertIsNone(parse_byte_range("bytes=1000-1001", 1000))


if __name__ == "__main__":
    unittest.main()
