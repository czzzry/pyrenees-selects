import json
import tempfile
import unittest
from pathlib import Path

from pyrenees_selects.selfie_review import SelfieReviewApplication, capture_time_from_filename


class SelfieReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "photos"
        self.source.mkdir()
        self.inventory = self.root / "face-inventory.tsv"
        self.state = self.root / "selfie-review.json"
        for filename in (
            "PXL_20240612_092115642.jpg",
            "PXL_20240609_112334278.jpg",
            "PXL_20240613_063111726.jpg",
        ):
            (self.source / filename).write_bytes(b"jpeg")
        self.inventory.write_text(
            "filename\tstatus\tface_count\n"
            "PXL_20240612_092115642.jpg\tlikely_selfie\t1\n"
            "PXL_20240609_112334278.jpg\tlikely_selfie\t1\n"
            "PXL_20240613_063111726.jpg\tpossible_face\t1\n",
            encoding="utf-8",
        )
        self.application = SelfieReviewApplication(
            self.source,
            self.inventory,
            self.state,
            static_dir=Path(__file__).parent.parent / "pyrenees_selects" / "static",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_inventory_keeps_only_likely_selfies_in_chronological_order(self) -> None:
        self.assertEqual(
            [photo.filename for photo in self.application.photos],
            ["PXL_20240609_112334278.jpg", "PXL_20240612_092115642.jpg"],
        )
        self.assertEqual(self.application.summary()["total"], 2)

    def test_decision_and_comment_persist_together(self) -> None:
        saved = self.application.save_photo(
            1,
            {"decision": "include", "comment": "Can we fix my closed eyes?"},
        )
        self.assertEqual(saved["summary"]["include"], 1)
        payload = json.loads(self.state.read_text(encoding="utf-8"))
        review = payload["reviews"]["PXL_20240609_112334278.jpg"]
        self.assertEqual(review["decision"], "include")
        self.assertEqual(review["comment"], "Can we fix my closed eyes?")

        reopened = SelfieReviewApplication(
            self.source,
            self.inventory,
            self.state,
            static_dir=Path(__file__).parent.parent / "pyrenees_selects" / "static",
        )
        self.assertEqual(reopened.state_payload()["photos"][0]["comment"], "Can we fix my closed eyes?")

    def test_decision_can_be_cleared_for_undo(self) -> None:
        self.application.save_photo(1, {"decision": "exclude"})
        result = self.application.save_photo(1, {"decision": None})
        self.assertEqual(result["summary"]["reviewed"], 0)
        self.assertIsNone(result["photo"]["decision"])

    def test_unknown_decision_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Decision must be"):
            self.application.save_photo(1, {"decision": "delete"})

    def test_capture_time_uses_filename_clock(self) -> None:
        captured, label = capture_time_from_filename("PXL_20240719_144518353.jpg")
        self.assertEqual(captured, "2024-07-19T14:45:18")
        self.assertEqual(label, "July 19, 2024 · 14:45")


if __name__ == "__main__":
    unittest.main()
