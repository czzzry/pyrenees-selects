import io
import json
import unittest

from pyrenees_selects.assistant import propose_sequence


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


class AssistantTests(unittest.TestCase):
    def test_openai_proposal_is_structured_path_free_and_not_applied(self):
        captured = {}

        def opener(request, timeout):
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.data)
            captured["timeout"] = timeout
            output = json.dumps({"selection_ids": ["selection_one"], "explanation": "Open on the quiet view."})
            return FakeResponse({"output": [{"type": "message", "content": [{"type": "output_text", "text": output}]}]})

        context = {
            "project": {"intent": "Quiet travel film", "target_duration": 30},
            "selections": [
                {"id": "selection_one", "decision": "keep", "comment": "quiet view"},
                {"id": "selection_skip", "decision": "skip", "comment": "do not use"},
            ],
        }
        proposal = propose_sequence(context, api_key="secret", opener=opener)
        self.assertEqual(proposal["payload"]["selection_ids"], ["selection_one"])
        self.assertEqual(proposal["kind"], "sequence")
        self.assertFalse(captured["body"]["store"])
        self.assertNotIn("secret", json.dumps(captured["body"]))
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret")

    def test_assistant_requires_an_eligible_selection(self):
        with self.assertRaises(ValueError):
            propose_sequence({"selections": []}, api_key="secret", opener=lambda *_a, **_k: None)


if __name__ == "__main__":
    unittest.main()
